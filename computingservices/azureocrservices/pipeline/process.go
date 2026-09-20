package pipeline

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"azureocrservice/config"
	"azureocrservice/httpx"
	"azureocrservice/logx"
	"azureocrservice/types"
)

type job struct {
	ctx           context.Context // per-document context (JobTimeout)
	parent        context.Context
	cfg           config.Config
	deps          Deps
	gates         Gates
	msg           types.QueueMessage
	docID         int64
	apim          string
	stage         string
	retries       int
	start         time.Time
	runningPosted bool // guards ocrjobrunning: onRunning may fire more than once
}

// Process runs one document end to end. It never panics or aborts the run:
// every outcome is a Result and, on failure, an ocrjobfailed status.
func Process(ctx context.Context, cfg config.Config, deps Deps, gates Gates, msg types.QueueMessage) (res Result) {
	jobCtx, cancel := context.WithTimeout(ctx, cfg.JobTimeout)
	defer cancel()
	j := &job{ctx: jobCtx, parent: ctx, cfg: cfg, deps: deps, gates: gates, msg: msg,
		docID: int64(msg.DocumentID), stage: "download", start: time.Now()}
	defer func() {
		if r := recover(); r != nil {
			res = j.fail(httpx.Coded("Panic", 1, fmt.Errorf("panic: %v", r)))
		}
	}()
	return j.run()
}

func (j *job) run() Result {
	path := j.msg.CompressedS3FilePath
	if path == "" {
		path = j.msg.S3FilePath
	}

	j.stage = "download"
	var src types.AnalyzeSource
	if j.cfg.UseBase64Source {
		data, err := j.deps.Store.Download(j.ctx, j.docID, path)
		if err != nil {
			return j.fail(err)
		}
		src.Base64 = base64.StdEncoding.EncodeToString(data)
	} else {
		u, err := j.deps.Store.PresignGet(path)
		if err != nil {
			return j.fail(err)
		}
		src.URL = u
	}

	j.stage = "submit"
	if err := j.gates.Submit.Wait(j.ctx); err != nil {
		return j.fail(err)
	}
	opLocation, apim, attempts, err := j.deps.Azure.Submit(j.ctx, j.docID, src)
	j.retries += max(attempts-1, 0)
	if err != nil {
		return j.fail(err)
	}
	j.apim = apim
	j.post("azureocrrequestcreated", map[string]any{"apimRequestID": apim, "operationLocation": opLocation}, "", 0, false)

	j.stage = "poll"
	_, attempts, err = j.deps.Azure.Poll(j.ctx, j.docID, opLocation, func() {
		if j.runningPosted {
			return
		}
		j.runningPosted = true
		j.post("ocrjobrunning", map[string]any{"apimRequestID": apim}, "", 0, false)
	})
	j.retries += max(attempts-1, 0)
	if err != nil {
		return j.fail(err)
	}

	j.stage = "result"
	pdf, attempts, err := j.deps.Azure.ResultPDF(j.ctx, j.docID, opLocation)
	j.retries += max(attempts-1, 0)
	if err != nil {
		return j.fail(err)
	}
	j.post("ocrjobsucceeded", map[string]any{"apimRequestID": apim, "pdfSize": len(pdf)}, "", 0, false)

	j.stage = "upload"
	key, size, err := j.upload(path, pdf)
	if err != nil {
		return j.fail(err)
	}
	if err := j.post("ocrfileuploadsuccess", map[string]any{"apimRequestID": apim}, key, int64(size), true); err != nil {
		_, attempts := httpx.CodeOf(err)
		return j.fail(httpx.Coded("ReviewerUnreachable", attempts, err))
	}

	dur := time.Since(j.start)
	logx.Event("JOB_DONE", "documentid", j.docID, "outcome", "success", "totalms", dur.Milliseconds(), "retries", j.retries)
	return Result{DocumentID: j.docID, Outcome: "success", Retries: j.retries, Duration: dur}
}

// upload acquires the shared upload semaphore and releases it via defer, so
// the permit is freed even if Store.Upload panics — Process recovers the
// panic higher up, and without this defer a panicking upload would leak the
// permit and starve every later job's Acquire until its JobTimeout.
func (j *job) upload(path string, pdf []byte) (key string, size int, err error) {
	if err := j.gates.Upload.Acquire(j.ctx, 1); err != nil {
		return "", 0, err
	}
	defer j.gates.Upload.Release(1)
	return j.deps.Store.Upload(j.ctx, j.docID, path, pdf)
}

// post sends one status row; failures are logged and returned, never fatal.
func (j *job) post(status string, message map[string]any, ocrPath string, size int64, hard bool) error {
	body, _ := json.Marshal(message)
	audit := types.DocReviewAudit{
		DocumentID: j.docID, MinistryRequestID: int64(j.msg.MinistryRequestId), DocumentMasterID: int64(j.msg.DocumentMasterID),
		Status: status, Description: string(body), OCRFilePath: ocrPath, OCRFileSize: size,
	}
	// Status posts use the parent context: a timed-out job must still report ocrjobfailed.
	err := j.deps.Reviewer.Post(context.WithoutCancel(j.parent), audit, hard)
	if err != nil {
		logx.Event("REVIEWER_POST_FAILED", "documentid", j.docID, "status", status, "err", err)
	}
	return err
}

func (j *job) fail(err error) Result {
	code, attempts := httpx.CodeOf(err)
	switch {
	case j.parent.Err() != nil:
		code = "Interrupted"
	case errors.Is(j.ctx.Err(), context.DeadlineExceeded):
		code = "JobTimeout"
	}
	dur := time.Since(j.start)
	res := Result{DocumentID: j.docID, Outcome: "failed", Stage: j.stage, Code: code, Reason: err.Error(),
		Attempts: attempts, Retries: j.retries, Duration: dur}
	j.post("ocrjobfailed", map[string]any{"stage": j.stage, "code": code, "reason": err.Error(), "attempts": attempts}, "", 0, true)
	logx.Event("JOB_FAILED", "documentid", j.docID, "stage", j.stage, "code", code, "reason", err.Error(),
		"attempts", attempts, "totalms", dur.Milliseconds(), "retries", j.retries)
	return res
}
