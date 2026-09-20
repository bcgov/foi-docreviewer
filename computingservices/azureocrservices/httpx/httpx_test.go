// httpx/httpx_test.go
package httpx

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func server(t *testing.T, codes ...int) (*httptest.Server, *atomic.Int32) {
	t.Helper()
	var n atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		i := int(n.Add(1)) - 1
		if i >= len(codes) {
			i = len(codes) - 1
		}
		if codes[i] == 429 && r.URL.Query().Get("ra") != "" {
			w.Header().Set("Retry-After", r.URL.Query().Get("ra"))
		}
		w.WriteHeader(codes[i])
	}))
	t.Cleanup(srv.Close)
	return srv, &n
}

func get(url string) func(context.Context) (*http.Request, error) {
	return func(ctx context.Context) (*http.Request, error) {
		return http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	}
}

func TestRetryableSet(t *testing.T) {
	for _, s := range []int{429, 500, 502, 503, 504} {
		if !Retryable(s) {
			t.Errorf("%d should be retryable", s)
		}
	}
	for _, s := range []int{200, 202, 400, 401, 403, 404, 413} {
		if Retryable(s) {
			t.Errorf("%d should not be retryable", s)
		}
	}
}

func TestRetryAfterSecondsIsHonoured(t *testing.T) {
	srv, n := server(t, 429, 200)
	var c429 Counter
	p := RetryPolicy{MaxRetries: 3, Base: 10 * time.Millisecond, Max: time.Second, On429: c429.Inc}
	start := time.Now()
	resp, attempts, err := DoWithRetry(context.Background(), srv.Client(), get(srv.URL+"/?ra=1"), p, "TEST", "documentid", 1)
	if err != nil || resp.StatusCode != 200 || attempts != 2 || n.Load() != 2 {
		t.Fatalf("resp=%v attempts=%d err=%v", resp, attempts, err)
	}
	if el := time.Since(start); el < time.Second {
		t.Fatalf("Retry-After: 1 not honoured, elapsed %s", el)
	}
	if c429.Load() != 1 {
		t.Fatalf("On429 called %d times", c429.Load())
	}
}

func TestBackoffWithoutHeaderAndBudget(t *testing.T) {
	srv, n := server(t, 503, 503, 503, 503)
	p := RetryPolicy{MaxRetries: 2, Base: 5 * time.Millisecond, Max: 20 * time.Millisecond}
	resp, attempts, err := DoWithRetry(context.Background(), srv.Client(), get(srv.URL), p, "TEST")
	if err != nil {
		t.Fatal(err)
	}
	if resp.StatusCode != 503 || attempts != 3 || n.Load() != 3 {
		t.Fatalf("status=%d attempts=%d sent=%d", resp.StatusCode, attempts, n.Load())
	}
}

func TestNonRetryableReturnsImmediately(t *testing.T) {
	srv, n := server(t, 400, 200)
	resp, attempts, _ := DoWithRetry(context.Background(), srv.Client(), get(srv.URL), RetryPolicy{MaxRetries: 5}, "TEST")
	if resp.StatusCode != 400 || attempts != 1 || n.Load() != 1 {
		t.Fatalf("status=%d attempts=%d", resp.StatusCode, attempts)
	}
}

func TestZeroRetriesIsSingleAttempt(t *testing.T) {
	srv, n := server(t, 429, 200)
	resp, attempts, _ := DoWithRetry(context.Background(), srv.Client(), get(srv.URL), RetryPolicy{}, "TEST")
	if resp.StatusCode != 429 || attempts != 1 || n.Load() != 1 {
		t.Fatalf("status=%d attempts=%d", resp.StatusCode, attempts)
	}
}

func TestContextCancelAbortsSleep(t *testing.T) {
	srv, _ := server(t, 429, 200)
	ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
	defer cancel()
	p := RetryPolicy{MaxRetries: 3, Base: 5 * time.Second, Max: 5 * time.Second}
	_, _, err := DoWithRetry(ctx, srv.Client(), get(srv.URL), p, "TEST")
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("want DeadlineExceeded, got %v", err)
	}
}

func TestTransportErrorIsRetriedThenReturned(t *testing.T) {
	p := RetryPolicy{MaxRetries: 1, Base: time.Millisecond, Max: time.Millisecond}
	_, attempts, err := DoWithRetry(context.Background(), &http.Client{Timeout: 200 * time.Millisecond},
		get("http://127.0.0.1:1/"), p, "TEST")
	if err == nil || attempts != 2 {
		t.Fatalf("attempts=%d err=%v", attempts, err)
	}
}

func TestRetryDelayHttpDate(t *testing.T) {
	now := time.Date(2026, 9, 19, 12, 0, 0, 0, time.UTC)
	resp := &http.Response{Header: http.Header{"Retry-After": []string{now.Add(3 * time.Second).Format(http.TimeFormat)}}}
	d := RetryDelay(resp, 0, RetryPolicy{Base: time.Second, Max: time.Minute}, now)
	if d != 3*time.Second {
		t.Fatalf("d=%s", d)
	}
}

func TestRetryDelayBackoffCapped(t *testing.T) {
	p := RetryPolicy{Base: time.Second, Max: 3 * time.Second}
	for attempt := 0; attempt < 6; attempt++ {
		d := RetryDelay(nil, attempt, p, time.Now())
		if d < 0 || d > 3*time.Second {
			t.Fatalf("attempt %d: %s outside [0,3s]", attempt, d)
		}
	}
	if d := RetryDelay(nil, 1, p, time.Now()); d < 2*time.Second {
		t.Fatalf("attempt 1 should be >= base*2 = 2s, got %s", d)
	}
}

func TestCodedError(t *testing.T) {
	err := error(Coded("PollTimeout", 4, errors.New("gave up")))
	wrapped := errors.Join(errors.New("outer"), err)
	code, attempts := CodeOf(wrapped)
	if code != "PollTimeout" || attempts != 4 {
		t.Fatalf("code=%s attempts=%d", code, attempts)
	}
	if code, attempts := CodeOf(errors.New("plain")); code != "Error" || attempts != 1 {
		t.Fatalf("default code=%s attempts=%d", code, attempts)
	}
	if err.Error() != "PollTimeout: gave up" {
		t.Fatalf("msg=%q", err.Error())
	}
}

func TestWithMinRetries(t *testing.T) {
	if p := (RetryPolicy{MaxRetries: 0}).WithMinRetries(2); p.MaxRetries != 2 {
		t.Fatal(p)
	}
	if p := (RetryPolicy{MaxRetries: 5}).WithMinRetries(2); p.MaxRetries != 5 {
		t.Fatal(p)
	}
}
