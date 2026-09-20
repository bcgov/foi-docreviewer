package pipeline

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"azureocrservice/httpservices"
	"azureocrservice/types"
)

type sliceSource struct {
	mu    sync.Mutex
	msgs  []types.QueueMessage
	i     int
	errAt int // if > 0, return errBroker once i == errAt
}

var errBroker = errors.New("broker 500")

func (s *sliceSource) Next(ctx context.Context) (types.QueueMessage, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.errAt > 0 && s.i == s.errAt {
		return types.QueueMessage{}, errBroker
	}
	if s.i >= len(s.msgs) {
		return types.QueueMessage{}, httpservices.ErrEOF
	}
	m := s.msgs[s.i]
	s.i++
	return m, nil
}

func messages(n int) []types.QueueMessage {
	out := make([]types.QueueMessage, n)
	for i := range out {
		out[i] = types.QueueMessage{DocumentID: 100 + i, S3FilePath: "http://s3/b/k.pdf"}
	}
	return out
}

func TestRunBoundsConcurrency(t *testing.T) {
	az, st, rv := happy()
	var inflight, peak atomic.Int32
	az.submit = func(context.Context, types.AnalyzeSource) (string, string, int, error) {
		n := inflight.Add(1)
		for {
			p := peak.Load()
			if n <= p || peak.CompareAndSwap(p, n) {
				break
			}
		}
		time.Sleep(20 * time.Millisecond)
		inflight.Add(-1)
		return "op", "apim", 1, nil
	}
	rv2 := &syncReviewer{inner: rv}
	c := cfg()
	c.MaxConcurrentJobs = 3
	sum := Run(context.Background(), c, &sliceSource{msgs: messages(10)}, Deps{Azure: az, Store: st, Reviewer: rv2})
	if sum.Pulled != 10 || sum.Succeeded != 10 || sum.Failed != 0 || len(sum.Results) != 10 {
		t.Fatalf("%+v", sum)
	}
	if peak.Load() > 3 || peak.Load() < 2 {
		t.Fatalf("peak in-flight = %d, want 2..3", peak.Load())
	}
}

func TestRunOnePanicDoesNotStopOthers(t *testing.T) {
	az, st, rv := happy()
	az.submit = func(_ context.Context, src types.AnalyzeSource) (string, string, int, error) {
		if src.Base64 == "" {
			panic("no source")
		}
		return "op", "apim", 1, nil
	}
	st.download = func(p string) ([]byte, error) {
		if p == "boom" {
			return []byte{}, nil // empty → empty base64 → submit panics
		}
		return []byte("%PDF"), nil
	}
	msgs := messages(5)
	msgs[2].S3FilePath = "boom"
	c := cfg()
	c.MaxConcurrentJobs = 2
	sum := Run(context.Background(), c, &sliceSource{msgs: msgs}, Deps{Azure: az, Store: st, Reviewer: &syncReviewer{inner: rv}})
	if sum.Succeeded != 4 || sum.Failed != 1 {
		t.Fatalf("%+v", sum)
	}
	var failed *Result
	for i := range sum.Results {
		if sum.Results[i].Outcome == "failed" {
			failed = &sum.Results[i]
		}
	}
	if failed == nil || failed.Code != "Panic" || failed.DocumentID != 102 {
		t.Fatalf("%+v", failed)
	}
}

func TestRunDequeueErrorFinishesInFlight(t *testing.T) {
	az, st, rv := happy()
	c := cfg()
	c.MaxConcurrentJobs = 2
	sum := Run(context.Background(), c, &sliceSource{msgs: messages(6), errAt: 3}, Deps{Azure: az, Store: st, Reviewer: &syncReviewer{inner: rv}})
	if sum.Pulled != 3 || sum.Succeeded != 3 || !errors.Is(sum.DequeueError, errBroker) {
		t.Fatalf("%+v", sum)
	}
}

func TestRunStopsPullingWhenInterrupted(t *testing.T) {
	az, st, rv := happy()
	ctx, cancel := context.WithCancel(context.Background())
	az.submit = func(context.Context, types.AnalyzeSource) (string, string, int, error) {
		cancel()
		return "op", "apim", 1, nil
	}
	c := cfg()
	c.MaxConcurrentJobs = 1
	sum := Run(ctx, c, &sliceSource{msgs: messages(5)}, Deps{Azure: az, Store: st, Reviewer: &syncReviewer{inner: rv}})
	if sum.Pulled != 1 {
		t.Fatalf("pulled %d after interrupt, want 1: %+v", sum.Pulled, sum)
	}
}

func TestSummaryIDs(t *testing.T) {
	s := Summary{Results: []Result{{DocumentID: 1, Outcome: "success"}, {DocumentID: 2, Outcome: "failed", Stage: "poll"}}}
	if s.IDs() != "1:ok,2:failed:poll" {
		t.Fatalf("%q", s.IDs())
	}
}

// syncReviewer makes fakeReviewer safe for concurrent workers.
type syncReviewer struct {
	mu    sync.Mutex
	inner *fakeReviewer
}

func (s *syncReviewer) Post(ctx context.Context, a types.DocReviewAudit, hard bool) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.inner.Post(ctx, a, hard)
}
