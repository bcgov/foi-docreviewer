package pipeline

import (
	"context"
	"errors"
	"strconv"
	"strings"
	"sync"
	"time"

	"azureocrservice/config"
	"azureocrservice/httpservices"
	"azureocrservice/logx"
)

type Summary struct {
	Pulled, Succeeded, Failed, Retries, HTTP429 int
	DequeueError                                error
	Results                                     []Result
	Duration                                    time.Duration
}

// IDs lists every processed document and its outcome, so the run's manifest
// is one grep away even though DEQUEUED lines are interleaved.
func (s Summary) IDs() string {
	parts := make([]string, 0, len(s.Results))
	for _, r := range s.Results {
		id := strconv.FormatInt(r.DocumentID, 10)
		if r.Outcome == "success" {
			parts = append(parts, id+":ok")
		} else {
			parts = append(parts, id+":failed:"+r.Stage)
		}
	}
	return strings.Join(parts, ",")
}

// Run pulls messages from src with MaxConcurrentJobs workers until the source
// is exhausted, fails, or ctx is cancelled. Each worker pulls only when free,
// so a hard kill loses at most MaxConcurrentJobs in-flight messages.
func Run(ctx context.Context, cfg config.Config, src httpservices.Source, deps Deps) Summary {
	start := time.Now()
	gates := NewGates(cfg)
	workers := cfg.MaxConcurrentJobs
	if workers < 1 {
		workers = 1
	}

	var (
		mu   sync.Mutex
		sum  Summary
		wg   sync.WaitGroup
		once sync.Once
	)
	record := func(r Result) {
		mu.Lock()
		defer mu.Unlock()
		sum.Results = append(sum.Results, r)
		sum.Retries += r.Retries
		if r.Outcome == "success" {
			sum.Succeeded++
		} else {
			sum.Failed++
		}
	}

	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func(worker int) {
			defer wg.Done()
			for ctx.Err() == nil {
				msg, err := src.Next(ctx)
				if err != nil {
					// A cancelled/deadline-exceeded run ctx surfaces through
					// Next as its own terminal error (ActiveMQSource stores
					// ctx.Err() as its err); that is "stop", not a dequeue
					// failure worth recording or logging.
					if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) || ctx.Err() != nil {
						return
					}
					if !errors.Is(err, httpservices.ErrEOF) {
						once.Do(func() {
							mu.Lock()
							sum.DequeueError = err
							mu.Unlock()
							logx.Event("DEQUEUE_ERROR", "worker", worker, "err", err)
						})
					}
					return
				}
				record(Process(ctx, cfg, deps, gates, msg))
			}
		}(w)
	}
	wg.Wait()

	sum.Pulled = len(sum.Results)
	sum.Duration = time.Since(start)
	if deps.HTTP429 != nil {
		sum.HTTP429 = deps.HTTP429.Load()
	}
	logx.Event("RUN_SUMMARY", "pulled", sum.Pulled, "succeeded", sum.Succeeded, "failed", sum.Failed,
		"retries", sum.Retries, "http429", sum.HTTP429, "dequeueError", errString(sum.DequeueError),
		"totalms", sum.Duration.Milliseconds(), "ids", sum.IDs())
	return sum
}

func errString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}
