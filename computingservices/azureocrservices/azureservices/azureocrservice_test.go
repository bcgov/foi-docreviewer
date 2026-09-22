// azureservices/azureocrservice_test.go
package azureservices

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"azureocrservice/httpx"
	"azureocrservice/types"
)

const resultsPath = "/documentintelligence/documentModels/prebuilt-read/analyzeResults/op-1"

type fake struct {
	submitCodes  []int    // per POST; last repeats
	pollBodies   []string // per GET status; last repeats; "429" means serve a 429
	pdfCodes     []int
	pdf          []byte
	posts, polls, pdfs atomic.Int32
	lastPostBody map[string]string
}

func (f *fake) server(t *testing.T) (*httptest.Server, *Client) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "prebuilt-read:analyze"):
			i := int(f.posts.Add(1)) - 1
			json.NewDecoder(r.Body).Decode(&f.lastPostBody)
			code := pick(f.submitCodes, i, 202)
			if code == 202 {
				w.Header().Set("Operation-Location", hostURL(r)+resultsPath+"?api-version=2024-11-30")
				w.Header().Set("Apim-Request-Id", "apim-1")
			}
			if code == 429 {
				w.Header().Set("Retry-After", "0")
			}
			if code == 400 {
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(400)
				w.Write([]byte(`{"error":{"code":"InvalidRequest","message":"bad source"}}`))
				return
			}
			w.WriteHeader(code)
		case r.Method == http.MethodGet && r.URL.Path == resultsPath+"/pdf":
			i := int(f.pdfs.Add(1)) - 1
			code := pick(f.pdfCodes, i, 200)
			w.WriteHeader(code)
			if code == 200 {
				w.Write(f.pdf)
			}
		case r.Method == http.MethodGet && r.URL.Path == resultsPath:
			i := int(f.polls.Add(1)) - 1
			body := f.pollBodies[min(i, len(f.pollBodies)-1)]
			if body == "429" {
				w.Header().Set("Retry-After", "0")
				w.WriteHeader(429)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.Write([]byte(body))
		default:
			w.WriteHeader(404)
		}
	}))
	t.Cleanup(srv.Close)
	c := New("key", srv.URL, Options{Timeout: time.Second, PollInterval: 5 * time.Millisecond, PollMaxAttempts: 10,
		Policy: httpx.RetryPolicy{MaxRetries: 2, Base: time.Millisecond, Max: 5 * time.Millisecond}})
	return srv, c
}

func hostURL(r *http.Request) string { return "http://" + r.Host }

func pick(codes []int, i, def int) int {
	if len(codes) == 0 {
		return def
	}
	return codes[min(i, len(codes)-1)]
}

func TestSubmitBase64Accepted(t *testing.T) {
	f := &fake{}
	_, c := f.server(t)
	op, apim, attempts, err := c.Submit(context.Background(), 1, types.AnalyzeSource{Base64: "AAAA"})
	if err != nil || apim != "apim-1" || attempts != 1 || !strings.HasSuffix(op, resultsPath+"?api-version=2024-11-30") {
		t.Fatalf("op=%s apim=%s attempts=%d err=%v", op, apim, attempts, err)
	}
	if f.lastPostBody["base64Source"] != "AAAA" || f.lastPostBody["urlSource"] != "" {
		t.Fatalf("body=%v", f.lastPostBody)
	}
}

func TestSubmitURLSource(t *testing.T) {
	f := &fake{}
	_, c := f.server(t)
	if _, _, _, err := c.Submit(context.Background(), 1, types.AnalyzeSource{URL: "https://s3/x?sig"}); err != nil {
		t.Fatal(err)
	}
	if f.lastPostBody["urlSource"] != "https://s3/x?sig" || f.lastPostBody["base64Source"] != "" {
		t.Fatalf("body=%v", f.lastPostBody)
	}
}

func TestSubmitRetriesOn429(t *testing.T) {
	f := &fake{submitCodes: []int{429, 429, 202}}
	_, c := f.server(t)
	_, _, attempts, err := c.Submit(context.Background(), 1, types.AnalyzeSource{Base64: "A"})
	if err != nil || attempts != 3 || f.posts.Load() != 3 {
		t.Fatalf("attempts=%d err=%v", attempts, err)
	}
}

func TestSubmit400CarriesAzureCode(t *testing.T) {
	f := &fake{submitCodes: []int{400}}
	_, c := f.server(t)
	_, _, _, err := c.Submit(context.Background(), 1, types.AnalyzeSource{Base64: "A"})
	code, attempts := httpx.CodeOf(err)
	if code != "InvalidRequest" || attempts != 1 || f.posts.Load() != 1 {
		t.Fatalf("code=%s attempts=%d err=%v", code, attempts, err)
	}
}

func TestPollRunningOnceThenSucceeded(t *testing.T) {
	f := &fake{pollBodies: []string{`{"status":"notStarted"}`, `{"status":"running"}`, `{"status":"running"}`, `{"status":"succeeded"}`}}
	srv, c := f.server(t)
	var running int
	id, attempts, err := c.Poll(context.Background(), 1, srv.URL+resultsPath+"?api-version=2024-11-30", func() { running++ })
	if err != nil || id != "op-1" || attempts != 4 || running != 1 {
		t.Fatalf("id=%s attempts=%d running=%d err=%v", id, attempts, running, err)
	}
}

func TestPoll429NeverFails(t *testing.T) {
	f := &fake{pollBodies: []string{"429", "429", "429", "429", `{"status":"succeeded"}`}}
	srv, c := f.server(t)
	c.opt.Policy.MaxRetries = 0 // even with no retry budget a throttled poll is not a failure
	_, attempts, err := c.Poll(context.Background(), 1, srv.URL+resultsPath, func() {})
	if err != nil || attempts != 5 {
		t.Fatalf("attempts=%d err=%v", attempts, err)
	}
}

func TestPollMaxAttemptsExhausted(t *testing.T) {
	f := &fake{pollBodies: []string{`{"status":"running"}`}}
	srv, c := f.server(t)
	c.opt.PollMaxAttempts = 3
	_, attempts, err := c.Poll(context.Background(), 1, srv.URL+resultsPath, func() {})
	if code, _ := httpx.CodeOf(err); code != "PollTimeout" || attempts != 3 {
		t.Fatalf("code=%s attempts=%d err=%v", code, attempts, err)
	}
}

func TestPollAzureFailedCarriesCode(t *testing.T) {
	f := &fake{pollBodies: []string{`{"status":"failed","error":{"code":"InvalidContent","message":"corrupt"}}`}}
	srv, c := f.server(t)
	_, _, err := c.Poll(context.Background(), 1, srv.URL+resultsPath, func() {})
	if code, _ := httpx.CodeOf(err); code != "InvalidContent" {
		t.Fatalf("code=%s err=%v", code, err)
	}
}

func TestResultPDFRetriesAndValidates(t *testing.T) {
	f := &fake{pdfCodes: []int{429, 200}, pdf: []byte("%PDF-1.4 ok")}
	srv, c := f.server(t)
	pdf, attempts, err := c.ResultPDF(context.Background(), 1, srv.URL+resultsPath+"?api-version=2024-11-30")
	if err != nil || attempts != 2 || string(pdf) != "%PDF-1.4 ok" {
		t.Fatalf("attempts=%d err=%v", attempts, err)
	}
	f2 := &fake{pdf: []byte("<html>")}
	srv2, c2 := f2.server(t)
	_, _, err = c2.ResultPDF(context.Background(), 1, srv2.URL+resultsPath)
	if code, _ := httpx.CodeOf(err); code != "NotPDF" {
		t.Fatalf("code=%s", code)
	}
}

func TestResultID(t *testing.T) {
	if id := ResultID("https://h" + resultsPath + "?api-version=2024-11-30"); id != "op-1" {
		t.Fatalf("id=%s", id)
	}
}
