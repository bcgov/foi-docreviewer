// Package httpservices pulls QueueMessages from the ActiveMQ REST API.
// The GET is a destructive receive: a message is gone from the broker once
// this returns it, so Next is only called by a worker that is free to
// process the message immediately (streaming dequeue).
package httpservices

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"sync"
	"time"

	"azureocrservice/config"
	"azureocrservice/logx"
	"azureocrservice/types"
)

var ErrEOF = errors.New("no more messages")

type Source interface {
	Next(ctx context.Context) (types.QueueMessage, error)
}

type ActiveMQSource struct {
	url, user, pass string
	limit           int
	client          *http.Client

	mu     sync.Mutex
	pulled int
	done   bool
	err    error
}

// NewSource builds the source from the same env keys the service has always
// used. URL construction is unchanged: "<activeMQBaseURL>://<queue>&clientId=<id>".
func NewSource(cfg config.Config, get func(string) string) *ActiveMQSource {
	url := fmt.Sprintf("%s://%s&clientId=%s", get("activeMQBaseURL"), get("foidococrqueue"), get("activemqclientid"))
	return NewActiveMQSource(url, get("activeMQUserName"), get("activeMQPassword"), cfg.BatchSize,
		&http.Client{Timeout: cfg.ActiveMQHTTPTimeout})
}

func NewActiveMQSource(url, user, pass string, limit int, client *http.Client) *ActiveMQSource {
	return &ActiveMQSource{url: url, user: user, pass: pass, limit: limit, client: client}
}

func (s *ActiveMQSource) Pulled() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.pulled
}

func (s *ActiveMQSource) Err() error {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.err
}

func (s *ActiveMQSource) Next(ctx context.Context) (types.QueueMessage, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for {
		if s.err != nil {
			return types.QueueMessage{}, s.err
		}
		if s.done || (s.limit > 0 && s.pulled >= s.limit) {
			return types.QueueMessage{}, ErrEOF
		}
		msg, ok, err := s.fetch(ctx)
		if err != nil {
			s.err = err
			return types.QueueMessage{}, err
		}
		if !ok {
			s.done = true
			return types.QueueMessage{}, ErrEOF
		}
		if msg == nil { // bad message: consumed but unusable, take the next one
			continue
		}
		s.pulled++
		logx.Event("DEQUEUED", "documentid", msg.DocumentID, "documentmasterid", msg.DocumentMasterID,
			"ministryrequestid", msg.MinistryRequestId, "pulled", s.pulled)
		return *msg, nil
	}
}

// fetch does one GET. Returns (nil, true, nil) for an unparseable message,
// (nil, false, nil) when the queue is empty (204 or client timeout).
func (s *ActiveMQSource) fetch(ctx context.Context) (*types.QueueMessage, bool, error) {
	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		req, err := http.NewRequestWithContext(ctx, http.MethodGet, s.url, nil)
		if err != nil {
			return nil, false, fmt.Errorf("failed to create HTTP request: %w", err)
		}
		req.Header.Set("Content-Type", "application/json")
		req.SetBasicAuth(s.user, s.pass)
		resp, err := s.client.Do(req)
		if err != nil {
			if isTimeout(err) {
				logx.Event("DEQUEUE_TIMEOUT", "attempt", attempt+1)
				return nil, false, nil
			}
			if ctx.Err() != nil {
				return nil, false, ctx.Err()
			}
			lastErr = fmt.Errorf("error making HTTP request: %w", err)
			logx.Event("DEQUEUE_RETRY", "attempt", attempt+1, "err", err)
			time.Sleep(time.Second)
			continue
		}
		body, readErr := io.ReadAll(resp.Body)
		resp.Body.Close()
		switch resp.StatusCode {
		case http.StatusNoContent:
			return nil, false, nil
		case http.StatusOK:
			if readErr != nil {
				return nil, false, fmt.Errorf("failed to read response body: %w", readErr)
			}
			var msg types.QueueMessage
			if err := json.Unmarshal(body, &msg); err != nil {
				logx.Event("DEQUEUE_BAD_MESSAGE", "err", err, "body", string(body))
				return nil, true, nil
			}
			return &msg, true, nil
		default:
			return nil, false, fmt.Errorf("unexpected response status: %s", resp.Status)
		}
	}
	return nil, false, lastErr
}

func isTimeout(err error) bool {
	var ne interface{ Timeout() bool }
	return errors.As(err, &ne) && ne.Timeout() || errors.Is(err, context.DeadlineExceeded)
}
