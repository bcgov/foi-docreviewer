package docreviewerocrservice

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"azureocrservice/httpx"
	"azureocrservice/types"
)

func TestPostSendsJSONWithSecret(t *testing.T) {
	var got types.DocReviewAudit
	var secret, path string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path, secret = r.URL.Path, r.Header.Get("X-FOI-OCR-Secret")
		json.NewDecoder(r.Body).Decode(&got)
		w.WriteHeader(http.StatusCreated)
	}))
	defer srv.Close()
	c := New(srv.URL, "s3cret", time.Second, httpx.RetryPolicy{})
	err := c.Post(context.Background(), types.DocReviewAudit{DocumentID: 7, Status: "ocrjobrunning", Description: `{"apimRequestID":"a"}`}, false)
	if err != nil || path != "/api/documentocrjob" || secret != "s3cret" || got.DocumentID != 7 || got.Status != "ocrjobrunning" {
		t.Fatalf("err=%v path=%s secret=%s got=%+v", err, path, secret, got)
	}
}

func TestPostHardRetriesEvenWithZeroBudget(t *testing.T) {
	var n atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if n.Add(1) < 3 {
			w.WriteHeader(502)
			return
		}
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	c := New(srv.URL, "s", time.Second, httpx.RetryPolicy{MaxRetries: 0, Base: time.Millisecond, Max: time.Millisecond})
	if err := c.Post(context.Background(), types.DocReviewAudit{Status: "ocrfileuploadsuccess"}, true); err != nil {
		t.Fatal(err)
	}
	if n.Load() != 3 {
		t.Fatalf("attempts=%d", n.Load())
	}
}

func TestPostSoftDoesNotRetryWithZeroBudget(t *testing.T) {
	var n atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		n.Add(1)
		w.WriteHeader(502)
	}))
	defer srv.Close()
	c := New(srv.URL, "s", time.Second, httpx.RetryPolicy{})
	err := c.Post(context.Background(), types.DocReviewAudit{Status: "ocrjobrunning"}, false)
	if err == nil || n.Load() != 1 {
		t.Fatalf("err=%v attempts=%d", err, n.Load())
	}
}
