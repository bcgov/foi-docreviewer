package s3services

import (
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
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

func TestUploadUsingPresignedURLSendsBody(t *testing.T) {
	var got []byte
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusOK)
	}))
	defer srv.Close()
	client := &http.Client{Timeout: time.Second}
	if err := UploadUsingPresignedURL(client, srv.URL+"/k?sig=1", []byte("%PDF-x")); err != nil {
		t.Fatal(err)
	}
	if string(got) != "%PDF-x" {
		t.Fatalf("body = %q", got)
	}
}

func TestUploadUsingPresignedURLNon200IsError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "denied", http.StatusForbidden)
	}))
	defer srv.Close()
	err := UploadUsingPresignedURL(&http.Client{Timeout: time.Second}, srv.URL, []byte("x"))
	if err == nil {
		t.Fatal("expected error")
	}
}
