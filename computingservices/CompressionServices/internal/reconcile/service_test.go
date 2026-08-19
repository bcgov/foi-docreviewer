package reconcile

import (
	"bytes"
	"context"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"compressionservices/internal/config"
	"compressionservices/internal/store"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var fixedNow = time.Date(2026, 8, 19, 12, 0, 0, 0, time.UTC)

func TestServiceRunOnceReconcilesFullBatchAndReturnsPreciseSummary(t *testing.T) {
	lockErr := errors.New("lock failed with password=lock-secret")
	failErr := errors.New("fail failed for /secret/document.pdf")
	repository := &fakeRepository{
		listJobs: []store.Job{
			candidate(11, 2, config.WorkloadNormal, true),
			candidate(12, 2, config.WorkloadNormal, true),
			candidate(13, 1, "", false),
			candidate(14, 2, config.WorkloadNormal, true),
			candidate(15, 2, config.WorkloadNormal, true),
			candidate(16, 1, config.WorkloadLarge, true),
			candidate(17, 2, config.WorkloadNormal, true),
		},
		lockResults: map[int]lockResult{
			11: {acquired: false},
			17: {err: lockErr},
		},
		latestResults: map[int]latestResult{
			12: {job: job(12, 3, store.StatusCompleted, config.WorkloadNormal, true, fixedNow)},
			13: {job: job(13, 1, store.StatusPushedToStream, "", false, fixedNow.Add(-76*time.Minute))},
			14: {job: job(14, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
			15: {job: job(15, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-19*time.Minute))},
			16: {job: job(16, 2, store.StatusStarted, "", false, fixedNow.Add(-76*time.Minute))},
		},
		failResults: map[int]failResult{
			13: {job: job(13, 3, store.StatusError, "", false, fixedNow)},
			14: {err: failErr},
			16: {job: job(16, 3, store.StatusError, "", false, fixedNow)},
		},
	}
	service := newTestService(repository, discardLogger())

	summary, err := service.RunOnce(context.Background())

	assert.Equal(t, Summary{
		Scanned:         7,
		Locked:          5,
		AlreadyTerminal: 1,
		Terminalized:    2,
		Failed:          2,
	}, summary)
	require.Error(t, err)
	assert.ErrorIs(t, err, lockErr)
	assert.ErrorIs(t, err, failErr)
	assert.NotContains(t, err.Error(), "lock-secret")
	assert.NotContains(t, err.Error(), "/secret/document.pdf")
	assert.Equal(t, 1, repository.listCalls)
	assert.Equal(t, testOptions().Thresholds, repository.gotThresholds)
	assert.Equal(t, 100, repository.gotLimit)
	assert.Equal(t, []int{11, 12, 13, 14, 15, 16, 17}, repository.lockCalls)
	assert.Equal(t, []int{12, 13, 14, 15, 16}, repository.latestCalls)
	assert.Equal(t, []int{13, 14, 16}, repository.failCalls)
	assert.Equal(t, []store.FailureCode{
		store.FailureCodeStaleUnfinished,
		store.FailureCodeStaleUnfinished,
		store.FailureCodeStaleUnfinished,
	}, repository.failCodes)
}

func TestServiceRunOnceUsesAuthoritativeLatestWorkloadAndTimestamp(t *testing.T) {
	repository := &fakeRepository{
		listJobs: []store.Job{
			candidate(21, 1, config.WorkloadNormal, true),
			candidate(22, 1, config.WorkloadLarge, true),
			candidate(23, 1, "", false),
			candidate(24, 1, config.WorkloadNormal, true),
		},
		latestResults: map[int]latestResult{
			// The workload changed to large and its latest row is not stale on that budget.
			21: {job: job(21, 2, store.StatusStarted, config.WorkloadLarge, true, fixedNow.Add(-30*time.Minute))},
			// The workload changed to normal and is stale on that budget.
			22: {job: job(22, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-30*time.Minute))},
			// A refreshed historical row is not stale on the conservative unknown budget.
			23: {job: job(23, 1, store.StatusPushedToStream, "", false, fixedNow.Add(-74*time.Minute))},
			// Equality with the cutoff matches ListStale's inclusive database predicate.
			24: {job: job(24, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-20*time.Minute))},
		},
	}
	service := newTestService(repository, discardLogger())

	summary, err := service.RunOnce(context.Background())

	require.NoError(t, err)
	assert.Equal(t, Summary{Scanned: 4, Locked: 4, Terminalized: 2}, summary)
	assert.Equal(t, []int{22, 24}, repository.failCalls)
}

func TestServiceRunOnceClassifiesTerminalConflictWinner(t *testing.T) {
	repository := &fakeRepository{
		listJobs: []store.Job{candidate(31, 2, config.WorkloadNormal, true)},
		latestResults: map[int]latestResult{
			31: {job: job(31, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
		},
		failResults: map[int]failResult{
			31: {job: job(31, 3, store.StatusSkipped, config.WorkloadNormal, true, fixedNow)},
		},
	}
	service := newTestService(repository, discardLogger())

	summary, err := service.RunOnce(context.Background())

	require.NoError(t, err)
	assert.Equal(t, Summary{
		Scanned:         1,
		Locked:          1,
		AlreadyTerminal: 1,
	}, summary)
}

func TestServiceRunOnceContinuesAfterRepositoryPanics(t *testing.T) {
	repository := &fakeRepository{
		listJobs: []store.Job{
			candidate(41, 2, config.WorkloadNormal, true),
			candidate(42, 2, config.WorkloadNormal, true),
			candidate(43, 2, config.WorkloadNormal, true),
			candidate(44, 2, config.WorkloadNormal, true),
		},
		lockResults: map[int]lockResult{
			41: {panicValue: "lock panic with secret"},
		},
		latestResults: map[int]latestResult{
			42: {panicValue: errors.New("latest panic with /secret/path")},
			43: {job: job(43, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
			44: {job: job(44, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
		},
		failResults: map[int]failResult{
			43: {panicValue: "fail panic with payload"},
		},
	}
	service := newTestService(repository, discardLogger())

	summary, err := service.RunOnce(context.Background())

	assert.Equal(t, Summary{Scanned: 4, Locked: 3, Terminalized: 1, Failed: 3}, summary)
	require.Error(t, err)
	assert.NotContains(t, err.Error(), "secret")
	assert.NotContains(t, err.Error(), "/secret/path")
	assert.NotContains(t, err.Error(), "payload")
	assert.Equal(t, []int{41, 42, 43, 44}, repository.lockCalls)
	assert.Equal(t, []int{42, 43, 44}, repository.latestCalls)
	assert.Equal(t, []int{43, 44}, repository.failCalls)
}

func TestServiceRunOnceRejectsMalformedRepositoryRowsWithoutTerminalizing(t *testing.T) {
	tests := []struct {
		name       string
		candidate  store.Job
		latest     latestResult
		failResult failResult
		wantLocked int
		wantFail   bool
	}{
		{
			name:      "candidate job ID is not positive",
			candidate: candidate(0, 2, config.WorkloadNormal, true),
		},
		{
			name:      "candidate version is terminal",
			candidate: candidate(51, 3, config.WorkloadNormal, true),
		},
		{
			name: "candidate timestamp is zero",
			candidate: store.Job{
				JobID:         51,
				Version:       2,
				Status:        store.StatusStarted,
				Workload:      config.WorkloadNormal,
				WorkloadKnown: true,
			},
		},
		{
			name:      "candidate known workload is impossible",
			candidate: candidate(51, 2, config.Workload("other"), true),
		},
		{
			name:       "latest job ID differs",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(52, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
			wantLocked: 1,
		},
		{
			name:      "latest timestamp is zero",
			candidate: candidate(51, 2, config.WorkloadNormal, true),
			latest: latestResult{job: store.Job{
				JobID:         51,
				Version:       2,
				Status:        store.StatusStarted,
				Workload:      config.WorkloadNormal,
				WorkloadKnown: true,
			}},
			wantLocked: 1,
		},
		{
			name:       "latest version is impossible",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(51, 4, store.StatusStarted, config.WorkloadNormal, true, fixedNow)},
			wantLocked: 1,
		},
		{
			name:       "latest known workload is impossible",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(51, 2, store.StatusStarted, config.Workload("other"), true, fixedNow.Add(-21*time.Minute))},
			wantLocked: 1,
		},
		{
			name:       "latest terminal status is impossible",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(51, 3, "mystery", config.WorkloadNormal, true, fixedNow)},
			wantLocked: 1,
		},
		{
			name:       "failure result has wrong job ID",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(51, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
			failResult: failResult{job: job(52, 3, store.StatusError, config.WorkloadNormal, true, fixedNow)},
			wantLocked: 1,
			wantFail:   true,
		},
		{
			name:       "failure result is not terminal",
			candidate:  candidate(51, 2, config.WorkloadNormal, true),
			latest:     latestResult{job: job(51, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute))},
			failResult: failResult{job: job(51, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow)},
			wantLocked: 1,
			wantFail:   true,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			repository := &fakeRepository{
				listJobs:      []store.Job{test.candidate},
				latestResults: map[int]latestResult{51: test.latest},
				failResults:   map[int]failResult{51: test.failResult},
			}
			service := newTestService(repository, discardLogger())

			summary, err := service.RunOnce(context.Background())

			require.Error(t, err)
			assert.Equal(t, Summary{Scanned: 1, Locked: test.wantLocked, Failed: 1}, summary)
			if test.wantFail {
				assert.Equal(t, []int{51}, repository.failCalls)
				return
			}
			assert.Empty(t, repository.failCalls)
		})
	}
}

func TestServiceRunOnceHonorsCancellationAndDoesNotStartLaterJobs(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	repository := &fakeRepository{
		listJobs: []store.Job{
			candidate(61, 2, config.WorkloadNormal, true),
			candidate(62, 2, config.WorkloadNormal, true),
		},
		latestFunc: func(latestCtx context.Context, jobID int) (store.Job, bool, error) {
			assert.NotNil(t, latestCtx.Done())
			cancel()
			return job(jobID, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute)), true, nil
		},
	}
	service := newTestService(repository, discardLogger())

	summary, err := service.RunOnce(ctx)

	assert.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, Summary{Scanned: 2, Locked: 1, Failed: 1}, summary)
	assert.Equal(t, []int{61}, repository.lockCalls)
	assert.Empty(t, repository.failCalls)
}

func TestServiceRunOnceAddsPerJobFinalizationDeadline(t *testing.T) {
	var latestDeadline time.Time
	var failDeadline time.Time
	repository := &fakeRepository{
		listJobs: []store.Job{candidate(71, 2, config.WorkloadNormal, true)},
		latestFunc: func(ctx context.Context, jobID int) (store.Job, bool, error) {
			var ok bool
			latestDeadline, ok = ctx.Deadline()
			require.True(t, ok)
			return job(jobID, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute)), true, nil
		},
		failFunc: func(ctx context.Context, jobID int, code store.FailureCode) (store.Job, error) {
			var ok bool
			failDeadline, ok = ctx.Deadline()
			require.True(t, ok)
			return job(jobID, 3, store.StatusError, config.WorkloadNormal, true, fixedNow), nil
		},
	}
	options := testOptions()
	options.FinalizationTimeout = 10 * time.Second
	service := New(repository, options, discardLogger())
	service.now = func() time.Time { return fixedNow }

	_, err := service.RunOnce(context.Background())

	require.NoError(t, err)
	assert.Equal(t, latestDeadline, failDeadline)
	remaining := time.Until(latestDeadline)
	assert.Positive(t, remaining)
	assert.LessOrEqual(t, remaining, 10*time.Second)
}

func TestServiceRunOnceValidatesServiceContextAndOptionsBeforeQuerying(t *testing.T) {
	validRepository := &fakeRepository{}
	var typedNilRepository *fakeRepository
	validOptions := testOptions()

	tests := []struct {
		name    string
		service *Service
		ctx     context.Context
	}{
		{name: "nil service", ctx: context.Background()},
		{name: "nil context", service: New(validRepository, validOptions, discardLogger())},
		{name: "nil repository", service: New(nil, validOptions, discardLogger()), ctx: context.Background()},
		{name: "typed nil repository", service: New(typedNilRepository, validOptions, discardLogger()), ctx: context.Background()},
		{name: "nil logger", service: New(validRepository, validOptions, nil), ctx: context.Background()},
		{
			name: "zero normal threshold",
			service: New(validRepository, Options{
				Thresholds: store.Thresholds{Large: time.Minute, Unknown: time.Minute},
				BatchSize:  1, FinalizationTimeout: time.Second,
			}, discardLogger()),
			ctx: context.Background(),
		},
		{
			name: "zero large threshold",
			service: New(validRepository, Options{
				Thresholds: store.Thresholds{Normal: time.Minute, Unknown: time.Minute},
				BatchSize:  1, FinalizationTimeout: time.Second,
			}, discardLogger()),
			ctx: context.Background(),
		},
		{
			name: "zero unknown threshold",
			service: New(validRepository, Options{
				Thresholds: store.Thresholds{Normal: time.Minute, Large: time.Minute},
				BatchSize:  1, FinalizationTimeout: time.Second,
			}, discardLogger()),
			ctx: context.Background(),
		},
		{
			name: "zero batch size",
			service: New(validRepository, Options{
				Thresholds:          store.Thresholds{Normal: time.Minute, Large: time.Minute, Unknown: time.Minute},
				FinalizationTimeout: time.Second,
			}, discardLogger()),
			ctx: context.Background(),
		},
		{
			name: "zero finalization timeout",
			service: New(validRepository, Options{
				Thresholds: store.Thresholds{Normal: time.Minute, Large: time.Minute, Unknown: time.Minute},
				BatchSize:  1,
			}, discardLogger()),
			ctx: context.Background(),
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var summary Summary
			var err error
			if test.service == nil {
				summary, err = test.service.RunOnce(test.ctx)
			} else {
				summary, err = test.service.RunOnce(test.ctx)
			}

			require.Error(t, err)
			assert.Equal(t, Summary{}, summary)
			assert.NotContains(t, err.Error(), "secret")
		})
	}
	assert.Zero(t, validRepository.listCalls)
}

func TestServiceRunOnceRejectsPreCanceledContextBeforeQuerying(t *testing.T) {
	repository := &fakeRepository{}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	summary, err := newTestService(repository, discardLogger()).RunOnce(ctx)

	assert.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, Summary{}, summary)
	assert.Zero(t, repository.listCalls)
}

func TestServiceRunOnceLogsOnlySafeAggregateAndFailureFields(t *testing.T) {
	var output bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&output, nil))
	repository := &fakeRepository{
		listJobs: []store.Job{candidate(81, 2, config.WorkloadNormal, true)},
		lockResults: map[int]lockResult{
			81: {err: errors.New("password=super-secret /records/private.pdf payload")},
		},
	}

	summary, err := newTestService(repository, logger).RunOnce(context.Background())

	require.Error(t, err)
	assert.Equal(t, Summary{Scanned: 1, Failed: 1}, summary)
	logs := output.String()
	assert.Equal(t, 3, strings.Count(strings.TrimSpace(logs), "\n")+1)
	assert.Contains(t, logs, `"msg":"compression reconciliation started"`)
	assert.Contains(t, logs, `"msg":"compression reconciliation job failed"`)
	assert.Contains(t, logs, `"job_id":81`)
	assert.Contains(t, logs, `"code":"database_unavailable"`)
	assert.Contains(t, logs, `"msg":"compression reconciliation completed"`)
	assert.Contains(t, logs, `"scanned":1`)
	assert.Contains(t, logs, `"failed":1`)
	assert.NotContains(t, logs, "super-secret")
	assert.NotContains(t, logs, "private.pdf")
	assert.NotContains(t, logs, "payload")
	assert.NotContains(t, logs, `"error"`)
}

func TestServiceRunOnceReturnsSafeListErrorAndCompletionLog(t *testing.T) {
	listErr := errors.New("database error contains password=list-secret")
	var output bytes.Buffer
	repository := &fakeRepository{listErr: listErr}

	summary, err := newTestService(
		repository,
		slog.New(slog.NewJSONHandler(&output, nil)),
	).RunOnce(context.Background())

	assert.Equal(t, Summary{}, summary)
	assert.ErrorIs(t, err, listErr)
	assert.NotContains(t, err.Error(), "list-secret")
	assert.Equal(t, 1, repository.listCalls)
	assert.Contains(t, output.String(), `"msg":"compression reconciliation completed"`)
	assert.NotContains(t, output.String(), "list-secret")
}

func newTestService(repository Repository, logger *slog.Logger) *Service {
	service := New(repository, testOptions(), logger)
	service.now = func() time.Time { return fixedNow }
	return service
}

func testOptions() Options {
	return Options{
		Thresholds: store.Thresholds{
			Normal:  20 * time.Minute,
			Large:   75 * time.Minute,
			Unknown: 75 * time.Minute,
		},
		BatchSize:           100,
		FinalizationTimeout: 10 * time.Second,
	}
}

func discardLogger() *slog.Logger {
	return slog.New(slog.NewJSONHandler(io.Discard, nil))
}

func candidate(jobID, version int, workload config.Workload, workloadKnown bool) store.Job {
	status := store.StatusPushedToStream
	if version == 2 {
		status = store.StatusStarted
	}
	return job(jobID, version, status, workload, workloadKnown, fixedNow.Add(-2*time.Hour))
}

func job(
	jobID int,
	version int,
	status string,
	workload config.Workload,
	workloadKnown bool,
	createdAt time.Time,
) store.Job {
	return store.Job{
		JobID:         jobID,
		Version:       version,
		Status:        status,
		Workload:      workload,
		WorkloadKnown: workloadKnown,
		CreatedAt:     createdAt,
	}
}

type lockResult struct {
	acquired   bool
	err        error
	panicValue any
}

type latestResult struct {
	job        store.Job
	found      bool
	err        error
	panicValue any
}

type failResult struct {
	job        store.Job
	err        error
	panicValue any
}

type fakeRepository struct {
	listJobs      []store.Job
	listErr       error
	listPanic     any
	lockResults   map[int]lockResult
	latestResults map[int]latestResult
	failResults   map[int]failResult
	latestFunc    func(context.Context, int) (store.Job, bool, error)
	failFunc      func(context.Context, int, store.FailureCode) (store.Job, error)

	listCalls     int
	gotThresholds store.Thresholds
	gotLimit      int
	lockCalls     []int
	latestCalls   []int
	failCalls     []int
	failCodes     []store.FailureCode
}

func (r *fakeRepository) ListStale(
	_ context.Context,
	thresholds store.Thresholds,
	limit int,
) ([]store.Job, error) {
	r.listCalls++
	r.gotThresholds = thresholds
	r.gotLimit = limit
	if r.listPanic != nil {
		panic(r.listPanic)
	}
	return r.listJobs, r.listErr
}

func (r *fakeRepository) WithinJobLock(
	ctx context.Context,
	jobID int,
	callback func(context.Context) error,
) (bool, error) {
	r.lockCalls = append(r.lockCalls, jobID)
	result, configured := r.lockResults[jobID]
	if configured {
		if result.panicValue != nil {
			panic(result.panicValue)
		}
		if result.err != nil || !result.acquired {
			return result.acquired, result.err
		}
	}
	return true, callback(ctx)
}

func (r *fakeRepository) Latest(ctx context.Context, jobID int) (store.Job, bool, error) {
	r.latestCalls = append(r.latestCalls, jobID)
	if r.latestFunc != nil {
		return r.latestFunc(ctx, jobID)
	}
	result, configured := r.latestResults[jobID]
	if !configured {
		return job(jobID, 2, store.StatusStarted, config.WorkloadNormal, true, fixedNow.Add(-21*time.Minute)), true, nil
	}
	if result.panicValue != nil {
		panic(result.panicValue)
	}
	if result.job != (store.Job{}) && !result.found {
		result.found = true
	}
	return result.job, result.found, result.err
}

func (r *fakeRepository) Fail(
	ctx context.Context,
	jobID int,
	code store.FailureCode,
) (store.Job, error) {
	r.failCalls = append(r.failCalls, jobID)
	r.failCodes = append(r.failCodes, code)
	if r.failFunc != nil {
		return r.failFunc(ctx, jobID, code)
	}
	result, configured := r.failResults[jobID]
	if !configured {
		return job(jobID, 3, store.StatusError, config.WorkloadNormal, true, fixedNow), nil
	}
	if result.panicValue != nil {
		panic(result.panicValue)
	}
	return result.job, result.err
}

var _ Repository = (*fakeRepository)(nil)
