package activemq

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"

	"ocrservices/models"
)

// ErrPermanent marks an ActiveMQ push that must not be retried (4xx).
var ErrPermanent = errors.New("activemq permanent error")

// Client posts OCR documents to the ActiveMQ REST endpoint.
type Client struct {
	http        *http.Client
	url         string
	username    string
	password    string
	destination string
}

// New builds a Client. base may be nil to use http.DefaultClient.
func New(base *http.Client, url, username, password, destination string) *Client {
	if base == nil {
		base = http.DefaultClient
	}
	return &Client{http: base, url: url, username: username, password: password, destination: destination}
}

// Push posts one message. 2xx → nil; 4xx → ErrPermanent-wrapped; transport
// error or 5xx → plain retryable error.
func (c *Client) Push(ctx context.Context, m models.OCRAzureMessage) error {
	body, err := json.Marshal(m)
	if err != nil {
		return fmt.Errorf("%w: marshal message: %v", ErrPermanent, err)
	}
	endpoint := c.url + "?destination=queue://" + c.destination
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("%w: build request: %v", ErrPermanent, err)
	}
	req.SetBasicAuth(c.username, c.password)
	req.Header.Set("Content-Type", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return fmt.Errorf("activemq request failed: %w", err)
	}
	defer resp.Body.Close()
	_, _ = io.Copy(io.Discard, resp.Body)
	switch {
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return nil
	case resp.StatusCode >= 400 && resp.StatusCode < 500:
		return fmt.Errorf("%w: activemq status %d", ErrPermanent, resp.StatusCode)
	default:
		return fmt.Errorf("activemq status %d", resp.StatusCode)
	}
}

// IsPermanent reports whether err is a non-retryable ActiveMQ failure.
func IsPermanent(err error) bool { return errors.Is(err, ErrPermanent) }
