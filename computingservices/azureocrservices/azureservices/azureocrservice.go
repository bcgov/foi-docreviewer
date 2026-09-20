// Package azureservices is the Azure Document Intelligence client: submit an
// Analyze job, poll it, fetch the searchable PDF. It posts no status and does
// no S3 work — pipeline.Process owns the sequence and the status contract.
package azureservices

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path"
	"strconv"
	"time"

	"azureocrservice/httpx"
	"azureocrservice/logx"
	"azureocrservice/types"
)

const apiVersion = "2024-11-30"

type Options struct {
	Timeout         time.Duration
	Policy          httpx.RetryPolicy
	PollInterval    time.Duration
	PollMaxAttempts int
}

type Client struct {
	key, baseURL string
	http         *http.Client
	opt          Options
}

func New(subscriptionKey, baseURL string, opt Options) *Client {
	return &Client{key: subscriptionKey, baseURL: baseURL, http: &http.Client{Timeout: opt.Timeout}, opt: opt}
}

// ResultID is the Azure operation id: the last path segment of Operation-Location.
func ResultID(opLocation string) string {
	u, err := url.Parse(opLocation)
	if err != nil {
		return ""
	}
	return path.Base(u.Path)
}

func (c *Client) Submit(ctx context.Context, docID int64, src types.AnalyzeSource) (string, string, int, error) {
	payload := map[string]string{}
	if src.URL != "" {
		payload["urlSource"] = src.URL
	} else {
		payload["base64Source"] = src.Base64
	}
	body, err := json.Marshal(payload)
	if err != nil {
		return "", "", 0, httpx.Coded("Marshal", 0, err)
	}
	postURL := fmt.Sprintf("%s/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=%s&output=pdf", c.baseURL, apiVersion)
	build := func(ctx context.Context) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, postURL, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Ocp-Apim-Subscription-Key", c.key)
		return req, nil
	}
	start := time.Now()
	resp, attempts, err := httpx.DoWithRetry(ctx, c.http, build, c.opt.Policy, "AZURE", "documentid", docID, "stage", "submit")
	if err != nil {
		return "", "", attempts, httpx.Coded("Transport", attempts, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusAccepted {
		return "", "", attempts, statusError(resp, attempts)
	}
	opLocation := resp.Header.Get("Operation-Location")
	apim := resp.Header.Get("Apim-Request-Id")
	if opLocation == "" || apim == "" {
		return "", "", attempts, httpx.Coded("MissingHeader", attempts, errors.New("missing Operation-Location or Apim-Request-Id"))
	}
	logx.Event("AZURE_SUBMIT", "documentid", docID, "opid", ResultID(opLocation), "apimRequestId", apim, "status", resp.StatusCode, "ms", logx.Ms(start))
	return opLocation, apim, attempts, nil
}

type statusBody struct {
	Status string `json:"status"`
	Error  struct {
		Code    string `json:"code"`
		Message string `json:"message"`
	} `json:"error"`
}

func (c *Client) Poll(ctx context.Context, docID int64, opLocation string, onRunning func()) (string, int, error) {
	opid := ResultID(opLocation)
	build := func(ctx context.Context) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, opLocation, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Ocp-Apim-Subscription-Key", c.key)
		req.Header.Set("Accept", "application/json")
		return req, nil
	}
	ran := false
	delay := c.opt.PollInterval
	for attempt := 1; attempt <= c.opt.PollMaxAttempts; attempt++ {
		if err := httpx.Sleep(ctx, delay); err != nil {
			return "", attempt, httpx.Coded("Interrupted", attempt, err)
		}
		delay = c.opt.PollInterval
		resp, _, err := httpx.DoWithRetry(ctx, c.http, build, c.opt.Policy, "AZURE", "documentid", docID, "stage", "poll")
		if err != nil {
			if ctx.Err() != nil {
				return "", attempt, httpx.Coded("Interrupted", attempt, ctx.Err())
			}
			logx.Event("AZURE_POLL", "documentid", docID, "opid", opid, "attempt", attempt, "status", "transport", "err", err)
			continue
		}
		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		if httpx.Retryable(resp.StatusCode) {
			// Throttled/unavailable after the retry budget: keep the operation, try again next tick.
			delay = httpx.RetryDelay(resp, 0, c.opt.Policy, time.Now())
			if delay < c.opt.PollInterval {
				delay = c.opt.PollInterval
			}
			logx.Event("AZURE_POLL", "documentid", docID, "opid", opid, "attempt", attempt, "status", resp.StatusCode, "retryAfter", delay)
			continue
		}
		if resp.StatusCode != http.StatusOK {
			return "", attempt, statusErrorBody(resp.StatusCode, body, attempt)
		}
		if readErr != nil {
			return "", attempt, httpx.Coded("Transport", attempt, readErr)
		}
		var sb statusBody
		if err := json.Unmarshal(body, &sb); err != nil {
			return "", attempt, httpx.Coded("BadStatusBody", attempt, err)
		}
		if ra, err := strconv.Atoi(resp.Header.Get("Retry-After")); err == nil && ra > 0 {
			delay = time.Duration(ra) * time.Second
		}
		logx.Event("AZURE_POLL", "documentid", docID, "opid", opid, "attempt", attempt, "status", sb.Status)
		switch sb.Status {
		case "notStarted", "running":
			if !ran {
				ran = true
				onRunning()
			}
		case "succeeded":
			return opid, attempt, nil
		case "failed":
			code := sb.Error.Code
			if code == "" {
				code = "AzureFailed"
			}
			return "", attempt, httpx.Coded(code, attempt, errors.New(sb.Error.Message))
		default:
			return "", attempt, httpx.Coded("UnknownStatus", attempt, fmt.Errorf("status %q", sb.Status))
		}
	}
	return "", c.opt.PollMaxAttempts, httpx.Coded("PollTimeout", c.opt.PollMaxAttempts,
		fmt.Errorf("operation %s not finished after %d polls", opid, c.opt.PollMaxAttempts))
}

func (c *Client) ResultPDF(ctx context.Context, docID int64, opLocation string) ([]byte, int, error) {
	u, err := url.Parse(opLocation)
	if err != nil {
		return nil, 0, httpx.Coded("BadOperationLocation", 0, err)
	}
	u.Path = u.Path + "/pdf"
	u.RawQuery = "api-version=" + apiVersion
	pdfURL := u.String()
	build := func(ctx context.Context) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, pdfURL, nil)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Ocp-Apim-Subscription-Key", c.key)
		return req, nil
	}
	start := time.Now()
	resp, attempts, err := httpx.DoWithRetry(ctx, c.http, build, c.opt.Policy, "AZURE", "documentid", docID, "stage", "result")
	if err != nil {
		return nil, attempts, httpx.Coded("Transport", attempts, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, attempts, statusError(resp, attempts)
	}
	pdf, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, attempts, httpx.Coded("Transport", attempts, err)
	}
	if !bytes.HasPrefix(pdf, []byte("%PDF")) {
		return nil, attempts, httpx.Coded("NotPDF", attempts, fmt.Errorf("result is not a PDF (%d bytes)", len(pdf)))
	}
	logx.Event("AZURE_RESULT_OK", "documentid", docID, "opid", ResultID(opLocation), "bytes", len(pdf), "ms", logx.Ms(start))
	return pdf, attempts, nil
}

func statusError(resp *http.Response, attempts int) error {
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	return statusErrorBody(resp.StatusCode, body, attempts)
}

// statusErrorBody turns a non-success response into a CodedError, using the
// Azure error envelope {"error":{"code","message"}} when the body carries one.
func statusErrorBody(status int, body []byte, attempts int) error {
	var sb statusBody
	if json.Unmarshal(body, &sb) == nil && sb.Error.Code != "" {
		return httpx.Coded(sb.Error.Code, attempts, fmt.Errorf("http %d: %s", status, sb.Error.Message))
	}
	return httpx.Coded("HTTP"+strconv.Itoa(status), attempts, fmt.Errorf("http %d: %s", status, bytes.TrimSpace(body)))
}
