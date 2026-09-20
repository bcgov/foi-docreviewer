package s3services

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"

	"azureocrservice/httpx"
)

func TestOCRKeyFor(t *testing.T) {
	cases := map[string]string{
		"requests/1/file.pdf":            "requests/1/fileOCR.pdf",
		"requests/1/file-compressed.pdf": "requests/1/file-compressedOCR.pdf",
		"noext":                          "noextOCR",
	}
	for in, want := range cases {
		if got := OCRKeyFor(in); got != want {
			t.Errorf("OCRKeyFor(%q) = %q, want %q", in, got, want)
		}
	}
}

func TestGenerateDownloadPresignedURLReturnsParseError(t *testing.T) {
	_, err := GenerateDownloadPresignedURL("http://host/bucketonly")
	if err == nil {
		t.Fatal("expected error for a path without an object key")
	}
}

func TestDownloadFromRetriesThenReturnsBytes(t *testing.T) {
	var n atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if n.Add(1) == 1 {
			w.WriteHeader(503)
			return
		}
		w.Write([]byte("%PDF-src"))
	}))
	defer srv.Close()
	s := NewStore(time.Second, httpx.RetryPolicy{MaxRetries: 2, Base: time.Millisecond, Max: time.Millisecond})
	data, err := s.DownloadFrom(context.Background(), 1, srv.URL+"/k?sig=1")
	if err != nil || string(data) != "%PDF-src" || n.Load() != 2 {
		t.Fatalf("data=%q n=%d err=%v", data, n.Load(), err)
	}
}

func TestDownloadFromEmptyAnd404(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/missing" {
			w.WriteHeader(404)
			return
		}
		w.WriteHeader(200)
	}))
	defer srv.Close()
	s := NewStore(time.Second, httpx.RetryPolicy{})
	_, err := s.DownloadFrom(context.Background(), 1, srv.URL+"/missing")
	if code, _ := httpx.CodeOf(err); code != "HTTP404" {
		t.Fatalf("code=%s err=%v", code, err)
	}
	_, err = s.DownloadFrom(context.Background(), 1, srv.URL+"/empty")
	if code, _ := httpx.CodeOf(err); code != "EmptyObject" {
		t.Fatalf("code=%s err=%v", code, err)
	}
}

func TestUploadToRetriesOn5xx(t *testing.T) {
	var n atomic.Int32
	var got []byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if n.Add(1) == 1 {
			w.WriteHeader(500)
			return
		}
		got, _ = io.ReadAll(r.Body)
		w.WriteHeader(200)
	}))
	defer srv.Close()
	s := NewStore(time.Second, httpx.RetryPolicy{MaxRetries: 1, Base: time.Millisecond, Max: time.Millisecond})
	size, err := s.UploadTo(context.Background(), 1, srv.URL+"/k?sig=1", []byte("%PDF-out"))
	if err != nil || size != 8 || string(got) != "%PDF-out" || n.Load() != 2 {
		t.Fatalf("size=%d got=%q n=%d err=%v", size, got, n.Load(), err)
	}
}
