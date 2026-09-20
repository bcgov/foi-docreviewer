// Package docreviewerocrservice posts DocumentOCRJob status rows to the
// reviewer API (POST /api/documentocrjob, X-FOI-OCR-Secret).
package docreviewerocrservice

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"azureocrservice/httpx"
	"azureocrservice/logx"
	"azureocrservice/types"
)

type Client struct {
	url, secret string
	http        *http.Client
	policy      httpx.RetryPolicy
}

func New(endpoint, secret string, timeout time.Duration, policy httpx.RetryPolicy) *Client {
	return &Client{url: fmt.Sprintf("%v/api/documentocrjob", endpoint), secret: secret,
		http: &http.Client{Timeout: timeout}, policy: policy}
}

// Post sends one DocReviewAudit row. hard=true raises the retry budget to at
// least 2 retries (3 attempts) for the statuses the UI depends on
// (ocrjobsucceeded, ocrfileuploadsuccess, ocrjobfailed).
func (c *Client) Post(ctx context.Context, audit types.DocReviewAudit, hard bool) error {
	body, err := json.Marshal(audit)
	if err != nil {
		return httpx.Coded("Marshal", 0, err)
	}
	build := func(ctx context.Context) (*http.Request, error) {
		req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.url, bytes.NewReader(body))
		if err != nil {
			return nil, err
		}
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-FOI-OCR-Secret", c.secret)
		return req, nil
	}
	policy := c.policy
	if hard {
		policy = policy.WithMinRetries(2)
	}
	resp, attempts, err := httpx.DoWithRetry(ctx, c.http, build, policy, "REVIEWER", "documentid", audit.DocumentID, "status", audit.Status)
	if err != nil {
		return httpx.Coded("Transport", attempts, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		msg, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return httpx.Coded(fmt.Sprintf("HTTP%d", resp.StatusCode), attempts, fmt.Errorf("reviewer api %d: %s", resp.StatusCode, msg))
	}
	logx.Event("REVIEWER_POST_OK", "documentid", audit.DocumentID, "status", audit.Status)
	return nil
}
