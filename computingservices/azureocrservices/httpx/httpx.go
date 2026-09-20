// httpx/httpx.go
// Package httpx is the single retry path for every outbound HTTP call
// (Azure, S3, reviewer API): 429/5xx/transport errors are retried with
// Retry-After or capped exponential backoff, bounded by RetryPolicy and ctx.
package httpx

import (
	"context"
	"errors"
	"fmt"
	"math"
	"math/rand"
	"net/http"
	"strconv"
	"sync/atomic"
	"time"

	"azureocrservice/logx"
)

type RetryPolicy struct {
	MaxRetries int
	Base, Max  time.Duration
	On429      func()
}

func (p RetryPolicy) WithMinRetries(n int) RetryPolicy {
	if p.MaxRetries < n {
		p.MaxRetries = n
	}
	return p
}

type Counter struct{ n atomic.Int64 }

func (c *Counter) Inc()      { c.n.Add(1) }
func (c *Counter) Load() int { return int(c.n.Load()) }

func Retryable(status int) bool {
	switch status {
	case http.StatusTooManyRequests, http.StatusInternalServerError, http.StatusBadGateway,
		http.StatusServiceUnavailable, http.StatusGatewayTimeout:
		return true
	}
	return false
}

// RetryDelay is the wait before retry number attempt (0-based). A Retry-After
// header (seconds or HTTP-date) wins; otherwise capped exponential backoff with jitter.
func RetryDelay(resp *http.Response, attempt int, p RetryPolicy, now time.Time) time.Duration {
	if resp != nil {
		if ra := resp.Header.Get("Retry-After"); ra != "" {
			if secs, err := strconv.Atoi(ra); err == nil && secs >= 0 {
				return time.Duration(secs) * time.Second
			}
			if at, err := http.ParseTime(ra); err == nil {
				if d := at.Sub(now); d > 0 {
					return d
				}
				return 0
			}
		}
	}
	base := p.Base
	if base <= 0 {
		base = time.Second
	}
	d := time.Duration(float64(base) * math.Pow(2, float64(attempt)))
	if d <= 0 { // overflow for a huge attempt number
		d = p.Max
	}
	d += time.Duration(rand.Int63n(int64(base)))
	if p.Max > 0 && d > p.Max {
		d = p.Max
	}
	return d
}

// DoWithRetry sends build(ctx) up to 1+MaxRetries times. It returns the last
// response even when its status is still retryable (budget exhausted); err is
// non-nil only for a transport error on the last attempt or ctx done.
// attempts = number of requests sent. marker names the log line: <marker>_RETRY.
func DoWithRetry(ctx context.Context, client *http.Client, build func(context.Context) (*http.Request, error),
	p RetryPolicy, marker string, kv ...any) (*http.Response, int, error) {
	for attempt := 0; ; attempt++ {
		req, err := build(ctx)
		if err != nil {
			return nil, attempt, fmt.Errorf("build request: %w", err)
		}
		resp, err := client.Do(req)
		attempts := attempt + 1
		if err == nil && !Retryable(resp.StatusCode) {
			return resp, attempts, nil
		}
		if err == nil && resp.StatusCode == http.StatusTooManyRequests && p.On429 != nil {
			p.On429()
		}
		if attempt >= p.MaxRetries {
			if err != nil {
				return nil, attempts, err
			}
			return resp, attempts, nil
		}
		delay := RetryDelay(resp, attempt, p, time.Now())
		status := 0
		if err == nil {
			status = resp.StatusCode
			resp.Body.Close()
		}
		fields := append(append([]any{}, kv...), "attempt", attempts, "status", status, "err", errOrEmpty(err), "retryAfter", delay)
		logx.Event(marker+"_RETRY", fields...)
		if err := Sleep(ctx, delay); err != nil {
			return nil, attempts, err
		}
	}
}

func errOrEmpty(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

// Sleep waits d or until ctx is done, returning ctx.Err() in the latter case.
func Sleep(ctx context.Context, d time.Duration) error {
	if d <= 0 {
		return ctx.Err()
	}
	t := time.NewTimer(d)
	defer t.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-t.C:
		return nil
	}
}

// CodedError carries a short machine-readable code and the attempt count into
// ocrjobfailed.message.
type CodedError struct {
	Code     string
	Attempts int
	Err      error
}

func (e *CodedError) Error() string { return e.Code + ": " + e.Err.Error() }
func (e *CodedError) Unwrap() error { return e.Err }

func Coded(code string, attempts int, err error) *CodedError {
	return &CodedError{Code: code, Attempts: attempts, Err: err}
}

func CodeOf(err error) (string, int) {
	var ce *CodedError
	if errors.As(err, &ce) {
		return ce.Code, ce.Attempts
	}
	return "Error", 1
}
