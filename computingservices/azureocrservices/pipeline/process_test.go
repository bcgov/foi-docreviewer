// pipeline/process_test.go
package pipeline

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"
	"time"

	"azureocrservice/config"
	"azureocrservice/httpx"
	"azureocrservice/types"
)

type fakeAzure struct {
	submit func(ctx context.Context, src types.AnalyzeSource) (string, string, int, error)
	poll   func(ctx context.Context, onRunning func()) (string, int, error)
	result func(ctx context.Context) ([]byte, int, error)
}

func (f *fakeAzure) Submit(ctx context.Context, _ int64, src types.AnalyzeSource) (string, string, int, error) {
	return f.submit(ctx, src)
}
func (f *fakeAzure) Poll(ctx context.Context, _ int64, _ string, onRunning func()) (string, int, error) {
	return f.poll(ctx, onRunning)
}
func (f *fakeAzure) ResultPDF(ctx context.Context, _ int64, _ string) ([]byte, int, error) {
	return f.result(ctx)
}

type fakeStore struct {
	download func(s3path string) ([]byte, error)
	upload   func(s3path string, pdf []byte) (string, int, error)
}

func (f *fakeStore) PresignGet(s3path string) (string, error) { return s3path + "?presigned", nil }
func (f *fakeStore) Download(_ context.Context, _ int64, s3path string) ([]byte, error) {
	return f.download(s3path)
}
func (f *fakeStore) Upload(_ context.Context, _ int64, s3path string, pdf []byte) (string, int, error) {
	return f.upload(s3path, pdf)
}

type fakeReviewer struct {
	posts   []types.DocReviewAudit
	failFor string // status whose Post returns an error
}

func (f *fakeReviewer) Post(_ context.Context, a types.DocReviewAudit, _ bool) error {
	f.posts = append(f.posts, a)
	if a.Status == f.failFor {
		return errors.New("reviewer down")
	}
	return nil
}

func (f *fakeReviewer) chain() []string {
	var out []string
	for _, p := range f.posts {
		out = append(out, p.Status)
	}
	return out
}

func happy() (*fakeAzure, *fakeStore, *fakeReviewer) {
	az := &fakeAzure{
		submit: func(_ context.Context, _ types.AnalyzeSource) (string, string, int, error) {
			return "https://az/analyzeResults/op-1?api-version=x", "apim-1", 2, nil
		},
		poll: func(_ context.Context, onRunning func()) (string, int, error) {
			onRunning()
			return "op-1", 3, nil
		},
		result: func(_ context.Context) ([]byte, int, error) { return []byte("%PDF-out"), 1, nil },
	}
	st := &fakeStore{
		download: func(string) ([]byte, error) { return []byte("%PDF-in"), nil },
		upload: func(s3path string, pdf []byte) (string, int, error) {
			return "http://s3/bucket/requests/1/fileOCR.pdf", len(pdf), nil
		},
	}
	return az, st, &fakeReviewer{}
}

var msg = types.QueueMessage{DocumentID: 456, DocumentMasterID: 789, MinistryRequestId: 123,
	S3FilePath: "http://s3/bucket/requests/1/file.pdf", CompressedS3FilePath: "http://s3/bucket/requests/1/file-compressed.pdf"}

func cfg() config.Config {
	c := config.LoadFrom(func(string) string { return "" })
	c.JobTimeout = 5 * time.Second
	return c
}

func failedMessage(t *testing.T, r *fakeReviewer) map[string]any {
	t.Helper()
	last := r.posts[len(r.posts)-1]
	if last.Status != "ocrjobfailed" {
		t.Fatalf("last status = %s", last.Status)
	}
	var m map[string]any
	if err := json.Unmarshal([]byte(last.Description), &m); err != nil {
		t.Fatalf("message not JSON: %q", last.Description)
	}
	return m
}

func TestProcessHappyPath(t *testing.T) {
	az, st, rv := happy()
	var uploadedTo string
	st.upload = func(s3path string, pdf []byte) (string, int, error) {
		uploadedTo = s3path
		return "http://s3/bucket/requests/1/file-compressedOCR.pdf", len(pdf), nil
	}
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Outcome != "success" || res.DocumentID != 456 || res.Retries != 3 {
		t.Fatalf("%+v", res)
	}
	want := []string{"azureocrrequestcreated", "ocrjobrunning", "ocrjobsucceeded", "ocrfileuploadsuccess"}
	if strings.Join(rv.chain(), ",") != strings.Join(want, ",") {
		t.Fatalf("chain=%v", rv.chain())
	}
	if uploadedTo != msg.CompressedS3FilePath {
		t.Fatalf("uploaded to %s", uploadedTo)
	}
	last := rv.posts[3]
	if last.OCRFilePath != "http://s3/bucket/requests/1/file-compressedOCR.pdf" || last.OCRFileSize != 8 {
		t.Fatalf("%+v", last)
	}
	if !strings.Contains(rv.posts[0].Description, `"operationLocation":"https://az/analyzeResults/op-1?api-version=x"`) ||
		!strings.Contains(rv.posts[2].Description, `"pdfSize":8`) {
		t.Fatalf("messages: %q / %q", rv.posts[0].Description, rv.posts[2].Description)
	}
	for _, p := range rv.posts {
		if p.DocumentID != 456 || p.DocumentMasterID != 789 || p.MinistryRequestID != 123 {
			t.Fatalf("ids wrong: %+v", p)
		}
	}
}

func TestProcessFallsBackToS3FilePath(t *testing.T) {
	az, st, rv := happy()
	var downloaded string
	st.download = func(p string) ([]byte, error) { downloaded = p; return []byte("%PDF"), nil }
	m := msg
	m.CompressedS3FilePath = ""
	Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), m)
	if downloaded != msg.S3FilePath {
		t.Fatalf("downloaded %s", downloaded)
	}
}

func TestProcessURLSourceMode(t *testing.T) {
	az, st, rv := happy()
	var got types.AnalyzeSource
	az.submit = func(_ context.Context, src types.AnalyzeSource) (string, string, int, error) {
		got = src
		return "op", "apim", 1, nil
	}
	c := cfg()
	c.UseBase64Source = false
	Process(context.Background(), c, Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(c), msg)
	if got.URL != msg.CompressedS3FilePath+"?presigned" || got.Base64 != "" {
		t.Fatalf("%+v", got)
	}
}

func TestProcessDownloadFailure(t *testing.T) {
	az, st, rv := happy()
	st.download = func(string) ([]byte, error) { return nil, httpx.Coded("HTTP404", 1, errors.New("not found")) }
	submitted := false
	az.submit = func(context.Context, types.AnalyzeSource) (string, string, int, error) {
		submitted = true
		return "", "", 0, nil
	}
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Outcome != "failed" || res.Stage != "download" || res.Code != "HTTP404" || submitted {
		t.Fatalf("%+v submitted=%v", res, submitted)
	}
	m := failedMessage(t, rv)
	if m["stage"] != "download" || m["code"] != "HTTP404" || m["attempts"] != float64(1) || len(rv.posts) != 1 {
		t.Fatalf("%v", m)
	}
}

func TestProcessPollFailureAfterCreated(t *testing.T) {
	az, st, rv := happy()
	az.poll = func(context.Context, func()) (string, int, error) {
		return "", 4, httpx.Coded("InvalidContent", 4, errors.New("corrupt"))
	}
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Stage != "poll" || res.Code != "InvalidContent" || res.Attempts != 4 {
		t.Fatalf("%+v", res)
	}
	if strings.Join(rv.chain(), ",") != "azureocrrequestcreated,ocrjobfailed" {
		t.Fatalf("chain=%v", rv.chain())
	}
}

func TestProcessJobTimeout(t *testing.T) {
	az, st, rv := happy()
	az.poll = func(ctx context.Context, _ func()) (string, int, error) {
		<-ctx.Done()
		return "", 1, httpx.Coded("Interrupted", 1, ctx.Err())
	}
	c := cfg()
	c.JobTimeout = 50 * time.Millisecond
	res := Process(context.Background(), c, Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(c), msg)
	if res.Outcome != "failed" || res.Stage != "poll" || res.Code != "JobTimeout" {
		t.Fatalf("%+v", res)
	}
}

func TestProcessInterrupted(t *testing.T) {
	az, st, rv := happy()
	ctx, cancel := context.WithCancel(context.Background())
	az.poll = func(ctx context.Context, _ func()) (string, int, error) {
		cancel()
		<-ctx.Done()
		return "", 1, ctx.Err()
	}
	res := Process(ctx, cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Code != "Interrupted" {
		t.Fatalf("%+v", res)
	}
}

func TestProcessPanicIsCaptured(t *testing.T) {
	az, st, rv := happy()
	az.submit = func(context.Context, types.AnalyzeSource) (string, string, int, error) { panic("boom") }
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Outcome != "failed" || res.Stage != "submit" || res.Code != "Panic" || !strings.Contains(res.Reason, "boom") {
		t.Fatalf("%+v", res)
	}
	if rv.chain()[len(rv.chain())-1] != "ocrjobfailed" {
		t.Fatalf("chain=%v", rv.chain())
	}
}

func TestProcessIntermediatePostFailureIsTolerated(t *testing.T) {
	az, st, rv := happy()
	rv.failFor = "ocrjobrunning"
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Outcome != "success" {
		t.Fatalf("%+v", res)
	}
}

func TestProcessFinalPostFailureFails(t *testing.T) {
	az, st, rv := happy()
	rv.failFor = "ocrfileuploadsuccess"
	res := Process(context.Background(), cfg(), Deps{Azure: az, Store: st, Reviewer: rv}, NewGates(cfg()), msg)
	if res.Outcome != "failed" || res.Stage != "upload" || res.Code != "ReviewerUnreachable" {
		t.Fatalf("%+v", res)
	}
}
