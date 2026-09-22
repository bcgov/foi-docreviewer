package httpservices

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"

	"azureocrservice/types"
)

// broker serves a fixed list of bodies then 204 forever.
type broker struct {
	mu     sync.Mutex
	bodies []string
	served int
	auth   string
	status int // if non-zero, always respond with this status
}

func (b *broker) handler(w http.ResponseWriter, r *http.Request) {
	b.mu.Lock()
	defer b.mu.Unlock()
	u, p, _ := r.BasicAuth()
	b.auth = u + ":" + p
	if b.status != 0 {
		w.WriteHeader(b.status)
		return
	}
	if b.served >= len(b.bodies) {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	body := b.bodies[b.served]
	b.served++
	w.Write([]byte(body))
}

func msgJSON(id int) string {
	b, _ := json.Marshal(types.QueueMessage{DocumentID: id, S3FilePath: "http://s3/b/k.pdf"})
	return string(b)
}

func newSource(t *testing.T, b *broker, limit int) *ActiveMQSource {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(b.handler))
	t.Cleanup(srv.Close)
	return NewActiveMQSource(srv.URL+"/api/message?destination=queue://foidococr&clientId=x", "admin", "pw", limit, &http.Client{Timeout: time.Second})
}

func drain(t *testing.T, s *ActiveMQSource) ([]int, error) {
	t.Helper()
	var ids []int
	for {
		m, err := s.Next(context.Background())
		if err != nil {
			return ids, err
		}
		ids = append(ids, m.DocumentID)
	}
}

func TestNextCapStopsAtLimit(t *testing.T) {
	b := &broker{bodies: []string{msgJSON(1), msgJSON(2), msgJSON(3), msgJSON(4), msgJSON(5), msgJSON(6), msgJSON(7), msgJSON(8)}}
	s := newSource(t, b, 5)
	ids, err := drain(t, s)
	if !errors.Is(err, ErrEOF) || len(ids) != 5 || s.Pulled() != 5 || b.served != 5 {
		t.Fatalf("ids=%v pulled=%d served=%d err=%v", ids, s.Pulled(), b.served, err)
	}
	if b.auth != "admin:pw" {
		t.Fatalf("auth=%s", b.auth)
	}
}

func TestNextZeroLimitDrainsUntil204(t *testing.T) {
	b := &broker{bodies: []string{msgJSON(1), msgJSON(2)}}
	s := newSource(t, b, 0)
	ids, err := drain(t, s)
	if !errors.Is(err, ErrEOF) || len(ids) != 2 {
		t.Fatalf("ids=%v err=%v", ids, err)
	}
	if _, err := s.Next(context.Background()); !errors.Is(err, ErrEOF) {
		t.Fatalf("second EOF: %v", err)
	}
}

func TestNextSkipsBadMessage(t *testing.T) {
	b := &broker{bodies: []string{msgJSON(1), "{not json", msgJSON(3)}}
	s := newSource(t, b, 0)
	ids, _ := drain(t, s)
	if len(ids) != 2 || ids[0] != 1 || ids[1] != 3 {
		t.Fatalf("ids=%v", ids)
	}
}

func TestNextUnexpectedStatusIsTerminalError(t *testing.T) {
	b := &broker{status: 500}
	s := newSource(t, b, 0)
	_, err := s.Next(context.Background())
	if err == nil || errors.Is(err, ErrEOF) {
		t.Fatalf("want error, got %v", err)
	}
	if _, err2 := s.Next(context.Background()); err2 != err {
		t.Fatalf("error should be cached: %v vs %v", err, err2)
	}
	if s.Err() == nil {
		t.Fatal("Err() should expose the terminal error")
	}
}

func TestNextClientTimeoutIsEOF(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(300 * time.Millisecond)
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()
	s := NewActiveMQSource(srv.URL, "a", "b", 0, &http.Client{Timeout: 50 * time.Millisecond})
	_, err := s.Next(context.Background())
	if !errors.Is(err, ErrEOF) || s.Err() != nil {
		t.Fatalf("err=%v Err()=%v", err, s.Err())
	}
}

func TestNextIsSafeForConcurrentWorkers(t *testing.T) {
	var bodies []string
	for i := 1; i <= 20; i++ {
		bodies = append(bodies, msgJSON(i))
	}
	s := newSource(t, &broker{bodies: bodies}, 0)
	var mu sync.Mutex
	seen := map[int]bool{}
	var wg sync.WaitGroup
	for w := 0; w < 4; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				m, err := s.Next(context.Background())
				if err != nil {
					return
				}
				mu.Lock()
				if seen[m.DocumentID] {
					t.Errorf("duplicate %d", m.DocumentID)
				}
				seen[m.DocumentID] = true
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	if len(seen) != 20 || s.Pulled() != 20 {
		t.Fatalf("seen=%d pulled=%d", len(seen), s.Pulled())
	}
}
