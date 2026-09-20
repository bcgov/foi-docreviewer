// Package pipeline owns the per-document sequence (download → submit → poll →
// result → upload) and the reviewer status contract, against three small
// interfaces so it can be tested without Azure, S3 or the reviewer API.
package pipeline

import (
	"context"
	"time"

	"golang.org/x/sync/semaphore"
	"golang.org/x/time/rate"

	"azureocrservice/config"
	"azureocrservice/httpx"
	"azureocrservice/types"
)

type Azure interface {
	Submit(ctx context.Context, docID int64, src types.AnalyzeSource) (opLocation, apimRequestID string, attempts int, err error)
	Poll(ctx context.Context, docID int64, opLocation string, onRunning func()) (resultID string, attempts int, err error)
	ResultPDF(ctx context.Context, docID int64, opLocation string) (pdf []byte, attempts int, err error)
}

type Store interface {
	PresignGet(s3path string) (string, error)
	Download(ctx context.Context, docID int64, s3path string) ([]byte, error)
	Upload(ctx context.Context, docID int64, s3path string, pdf []byte) (key string, size int, err error)
}

type Reviewer interface {
	Post(ctx context.Context, audit types.DocReviewAudit, hard bool) error
}

type Deps struct {
	Azure    Azure
	Store    Store
	Reviewer Reviewer
	HTTP429  *httpx.Counter // may be nil
}

// Gates are shared by every worker of a run: Analyze submissions per second
// and concurrent S3 PUTs.
type Gates struct {
	Submit *rate.Limiter
	Upload *semaphore.Weighted
}

func NewGates(cfg config.Config) Gates {
	limit := rate.Inf
	if cfg.AnalyzeRatePerSec > 0 {
		limit = rate.Limit(cfg.AnalyzeRatePerSec)
	}
	uploads := int64(cfg.UploadConcurrency)
	if uploads < 1 {
		uploads = 1
	}
	return Gates{Submit: rate.NewLimiter(limit, 1), Upload: semaphore.NewWeighted(uploads)}
}

type Result struct {
	DocumentID          int64
	Outcome             string
	Stage, Code, Reason string
	Attempts, Retries   int
	Duration            time.Duration
}
