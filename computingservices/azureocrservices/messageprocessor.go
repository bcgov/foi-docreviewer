package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"time"

	"azureocrservice/azureservices"
	"azureocrservice/config"
	"azureocrservice/httpservices"
	"azureocrservice/logx"
	"azureocrservice/runlock"
	"azureocrservice/s3services"
)

func main() { os.Exit(run()) }

// run is the scheduled unit of work: one dequeue-and-process pass.
// Exit code 1 only when the lock cannot be evaluated or the dequeue failed
// before any message was processed; per-document failures never fail the run.
func run() int {
	start := time.Now()
	cfg := config.Load()

	y, m, d := start.Date()
	filedate := strconv.Itoa(y) + "-" + strconv.Itoa(int(m)) + "-" + strconv.Itoa(d)
	file, err := os.OpenFile(cfg.LogFilePath+filedate+"dococrlog.txt", os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		fmt.Println("Error opening file:", err)
		return 1
	}
	defer file.Close()
	os.Stdout = file // every logx.Event and fmt.Print goes to the daily file
	fmt.Println("\nStart Time :" + start.String())

	release, err := runlock.Acquire(cfg.RunLockPath, 2*cfg.JobTimeout)
	if err != nil {
		if errors.Is(err, runlock.ErrHeld) {
			logx.Event("RUNLOCK_HELD", "path", cfg.RunLockPath, "err", err)
			return 0
		}
		logx.Event("RUNLOCK_ERROR", "path", cfg.RunLockPath, "err", err)
		return 1
	}
	defer release()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	logx.Event("RUN_START", "batchsize", cfg.BatchSize, "concurrency", cfg.MaxConcurrentJobs,
		"ratelimit", cfg.AnalyzeRatePerSec, "pollinterval", cfg.PollInterval, "maxretries", cfg.MaxRetries,
		"jobtimeout", cfg.JobTimeout, "lock", cfg.RunLockPath)

	dequeuedmessages, err := httpservices.ProcessMessage()
	if err != nil {
		logx.Event("DEQUEUE_ERROR", "err", err)
		return 1
	}
	succeeded, failed := 0, 0
	for _, message := range dequeuedmessages {
		if ctx.Err() != nil {
			logx.Event("RUN_INTERRUPTED", "remaining", len(dequeuedmessages)-succeeded-failed)
			break
		}
		fmt.Printf("Received message: %+v\n", message)
		filePathForOCR := message.CompressedS3FilePath
		if filePathForOCR == "" {
			filePathForOCR = message.S3FilePath
		}
		jobStart := time.Now()
		pdf, err := getBytesfromDocumentPath(filePathForOCR, cfg.S3HTTPTimeout)
		if err != nil {
			failed++
			logx.Event("JOB_FAILED", "documentid", message.DocumentID, "stage", "download", "reason", err, "totalms", logx.Ms(jobStart))
			continue
		}
		if _, err := azureservices.CallAzureOCRService(pdf, message, filePathForOCR, cfg.AzureHTTPTimeout); err != nil {
			failed++
			logx.Event("JOB_FAILED", "documentid", message.DocumentID, "stage", "ocr", "reason", err, "totalms", logx.Ms(jobStart))
			continue
		}
		succeeded++
		logx.Event("JOB_DONE", "documentid", message.DocumentID, "outcome", "success", "totalms", logx.Ms(jobStart))
	}
	logx.Event("RUN_SUMMARY", "pulled", len(dequeuedmessages), "succeeded", succeeded, "failed", failed, "totalms", logx.Ms(start))
	fmt.Println("End Time :" + time.Now().String())
	return 0
}

// getBytesfromDocumentPath presigns a GET for the source object and downloads
// it. An empty body is an error: never send an empty base64Source to Azure.
func getBytesfromDocumentPath(documenturlpath string, timeout time.Duration) ([]byte, error) {
	s3url, err := s3services.GenerateDownloadPresignedURL(documenturlpath)
	if err != nil {
		return nil, fmt.Errorf("presign download: %w", err)
	}
	client := &http.Client{Timeout: timeout}
	resp, err := client.Get(s3url)
	if err != nil {
		return nil, fmt.Errorf("download: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("download: status %d", resp.StatusCode)
	}
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("download: read body: %w", err)
	}
	if len(data) == 0 {
		return nil, errors.New("download: empty body")
	}
	return data, nil
}
