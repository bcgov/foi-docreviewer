package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"time"

	"azureocrservice/azureservices"
	"azureocrservice/config"
	"azureocrservice/docreviewerocrservice"
	"azureocrservice/httpservices"
	"azureocrservice/httpx"
	"azureocrservice/logx"
	"azureocrservice/pipeline"
	"azureocrservice/runlock"
	"azureocrservice/s3services"
	"azureocrservice/utils"
)

func main() { os.Exit(run()) }

// run is the scheduled unit of work: one dequeue-and-process pass.
// Exit code 1 only when the lock cannot be evaluated or the dequeue failed
// before any message was processed; per-document failures never fail the run.
func run() int {
	start := time.Now()

	// Redirect stdout before config.Load so its CONFIG_DEFAULT lines reach the
	// daily file (the console is discarded under Task Scheduler). logfilepath is
	// read from the same key config.Load uses, so cfg.LogFilePath matches.
	y, m, d := start.Date()
	filedate := strconv.Itoa(y) + "-" + strconv.Itoa(int(m)) + "-" + strconv.Itoa(d)
	file, err := os.OpenFile(utils.ViperEnvVariable("logfilepath")+filedate+"dococrlog.txt", os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)
	if err != nil {
		fmt.Println("Error opening file:", err)
		return 1
	}
	defer file.Close()
	os.Stdout = file // every logx.Event and fmt.Print goes to the daily file
	fmt.Println("\nStart Time :" + start.String())

	cfg := config.Load()

	release, err := runlock.Acquire(cfg.RunLockPath, 2*cfg.JobTimeout)
	if err != nil {
		if errors.Is(err, runlock.ErrHeld) {
			logx.Event("RUNLOCK_HELD", "path", cfg.RunLockPath, "err", err)
			return 0
		}
		logx.Event("RUNLOCK_ERROR", "path", cfg.RunLockPath, "err", err)
		return 1
	}
	defer release()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	logx.Event("RUN_START", "batchsize", cfg.BatchSize, "concurrency", cfg.MaxConcurrentJobs,
		"ratelimit", cfg.AnalyzeRatePerSec, "pollinterval", cfg.PollInterval, "maxretries", cfg.MaxRetries,
		"jobtimeout", cfg.JobTimeout, "lock", cfg.RunLockPath)

	counter := &httpx.Counter{}
	deps := buildDeps(cfg, counter)

	src := httpservices.NewSource(cfg, utils.ViperEnvVariable)
	sum := pipeline.Run(ctx, cfg, src, deps)
	fmt.Println("End Time :" + time.Now().String())
	if sum.DequeueError != nil && sum.Pulled == 0 {
		return 1
	}
	return 0
}

// buildDeps constructs the real Azure, S3 and reviewer clients from config.
// The 429 counter is shared so RUN_SUMMARY can report throttling across all of them.
func buildDeps(cfg config.Config, counter *httpx.Counter) pipeline.Deps {
	policy := httpx.RetryPolicy{MaxRetries: cfg.MaxRetries, Base: cfg.RetryBase, Max: cfg.RetryMax, On429: counter.Inc}
	return pipeline.Deps{
		Azure: azureservices.New(utils.ViperEnvVariable("azuresubcriptionkey"), utils.ViperEnvVariable("azuredocumentocraiendpoint"),
			azureservices.Options{Timeout: cfg.AzureHTTPTimeout, Policy: policy, PollInterval: cfg.PollInterval, PollMaxAttempts: cfg.PollMaxAttempts}),
		Store:    s3services.NewStore(cfg.S3HTTPTimeout, policy),
		Reviewer: docreviewerocrservice.New(utils.ViperEnvVariable("docreviewerocrapiendpoint"), utils.ViperEnvVariable("docreviewerocrapisecret"), cfg.ReviewerTimeout, policy),
		HTTP429:  counter,
	}
}
