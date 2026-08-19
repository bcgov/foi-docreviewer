package compression

import (
	"context"
	"errors"
	"testing"
	"time"

	"compressionservices/internal/config"
	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var fixedNow = time.Now().UTC().Truncate(time.Second)

func TestProcessExistingTerminalStatesShortCircuit(t *testing.T) {
	tests := []struct {
		name          string
		status        string
		wantFollowUps int
	}{
		{name: "completed follows up", status: store.StatusCompleted, wantFollowUps: 1},
		{name: "skipped follows up", status: store.StatusSkipped, wantFollowUps: 1},
		{name: "error does not follow up", status: store.StatusError},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.latest = terminalJob(tt.status)
			processor := &fakeProcessor{}
			followUp := &fakeFollowUp{}

			err := newTestHandler(repo, processor, followUp).Process(
				context.Background(),
				delivery(41),
			)

			require.NoError(t, err)
			assert.Zero(t, processor.calls)
			assert.Zero(t, repo.ensureStartedCalls)
			assert.Equal(t, tt.wantFollowUps, followUp.calls)
		})
	}
}

func TestProcessRejectsUnconfirmedExistingVersionThree(t *testing.T) {
	tests := []struct {
		name   string
		latest store.Job
	}{
		{
			name:   "unknown status",
			latest: terminalJob(store.StatusStarted),
		},
		{
			name: "wrong job identifier",
			latest: store.Job{
				JobID:     99,
				Version:   3,
				Status:    store.StatusCompleted,
				CreatedAt: fixedNow,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.latest = tt.latest
			followUp := &fakeFollowUp{}

			err := newTestHandler(repo, &fakeProcessor{}, followUp).Process(
				context.Background(),
				delivery(41),
			)

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
			assert.True(t, IsRetryable(err))
			assert.Zero(t, followUp.calls)
			assert.Zero(t, repo.ensureStartedCalls)
		})
	}
}

func TestProcessLockContentionReturnsSafeRetryableFailure(t *testing.T) {
	repo := newFakeRepository()
	repo.contended = true
	processor := &fakeProcessor{}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.latestCalls)
	assert.Zero(t, processor.calls)
}

func TestProcessLockFailurePreservesCauseWithoutExposingIt(t *testing.T) {
	repoCause := errors.New("database host secret.internal unavailable")
	repo := newFakeRepository()
	repo.lockErr = repoCause

	err := newTestHandler(repo, &fakeProcessor{}, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.NotContains(t, err.Error(), "secret.internal")
	assert.ErrorIs(t, err, repoCause)
	assert.True(t, IsRetryable(err))
}

func TestProcessDoesNotSucceedWhenLockCallbackWasNotInvoked(t *testing.T) {
	repo := newFakeRepository()
	repo.skipCallback = true

	err := newTestHandler(repo, &fakeProcessor{}, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.latestCalls)
}

func TestProcessWorkloadMismatchTerminalizesUnderLock(t *testing.T) {
	tests := []struct {
		name     string
		delivery config.Workload
		latest   store.Job
		started  store.Job
	}{
		{
			name:     "delivery disagrees with configured workload",
			delivery: config.WorkloadLarge,
			latest:   startedJob(config.WorkloadNormal),
		},
		{
			name:     "stored workload disagrees with configured workload",
			delivery: config.WorkloadNormal,
			latest:   startedJob(config.WorkloadLarge),
		},
		{
			name:     "authoritative started workload disagrees",
			delivery: config.WorkloadNormal,
			latest: store.Job{
				JobID:         41,
				Version:       1,
				Status:        store.StatusPushedToStream,
				WorkloadKnown: false,
				CreatedAt:     fixedNow,
			},
			started: startedJob(config.WorkloadLarge),
		},
		{
			name:     "authoritative started workload is unknown",
			delivery: config.WorkloadNormal,
			latest: store.Job{
				JobID:         41,
				Version:       1,
				Status:        store.StatusPushedToStream,
				WorkloadKnown: false,
				CreatedAt:     fixedNow,
			},
			started: store.Job{
				JobID:         41,
				Version:       2,
				Status:        store.StatusStarted,
				WorkloadKnown: false,
				CreatedAt:     fixedNow,
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.latest = tt.latest
			if tt.started.Version != 0 {
				repo.started = tt.started
			}
			processor := &fakeProcessor{}
			d := delivery(41)
			d.Workload = tt.delivery

			err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(context.Background(), d)

			require.NoError(t, err)
			assert.Equal(t, store.FailureCodeWorkloadMismatch, repo.failureCode)
			assert.True(t, repo.failWhileLocked)
			assert.Zero(t, processor.calls)
		})
	}
}

func TestProcessRedeliveryUsesOriginalDeadline(t *testing.T) {
	started := time.Date(2026, 8, 18, 12, 0, 0, 0, time.UTC)
	repo := newFakeRepository()
	repo.latest = store.Job{
		JobID:         41,
		Version:       2,
		Status:        store.StatusStarted,
		Workload:      config.WorkloadNormal,
		WorkloadKnown: true,
		CreatedAt:     started,
	}
	repo.started = repo.latest
	processor := &fakeProcessor{}
	handler := NewHandler(repo, processor, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   15 * time.Minute,
		FinalizationTimeout: 10 * time.Second,
		Now:                 func() time.Time { return started.Add(16 * time.Minute) },
	})

	err := handler.Process(context.Background(), delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.Zero(t, processor.calls)
}

func TestProcessUsesAuthoritativeStartedDeadline(t *testing.T) {
	started := fixedNow.Add(-5 * time.Minute)
	repo := newFakeRepository()
	repo.latest = store.Job{
		JobID:         41,
		Version:       1,
		Status:        store.StatusPushedToStream,
		Workload:      config.WorkloadNormal,
		WorkloadKnown: true,
		CreatedAt:     fixedNow.Add(-time.Hour),
	}
	repo.started = startedJob(config.WorkloadNormal)
	repo.started.CreatedAt = started
	processor := &fakeProcessor{result: completedResult()}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	require.NotNil(t, processor.deadline)
	assert.Equal(t, started.Add(15*time.Minute), *processor.deadline)
}

func TestProcessProcessorDeadlineTerminalizesWithDetachedContext(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	processor := &fakeProcessor{waitForContext: true}
	handler := NewHandler(repo, processor, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   40 * time.Millisecond,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(context.Background(), delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.False(t, repo.failContextCanceled)
	assert.True(t, repo.failWhileLocked)
}

func TestProcessCallerCancellationRemainsRetryable(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithCancel(context.Background())
	processor := &fakeProcessor{
		after:          cancel,
		waitForContext: true,
	}
	handler := NewHandler(repo, processor, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   time.Second,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.ErrorIs(t, err, context.Canceled)
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.failCalls)
}

func TestProcessEarlierCallerDeadlineRemainsRetryable(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Millisecond)
	defer cancel()
	processor := &fakeProcessor{waitForContext: true}
	handler := NewHandler(repo, processor, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   time.Second,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.ErrorIs(t, err, context.DeadlineExceeded)
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.failCalls)
}

func TestProcessJobDeadlineBeforeLaterCallerCancellationTerminalizesTimeout(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	processor := &fakeProcessor{
		waitForContext:   true,
		afterContextDone: cancel,
	}
	handler := NewHandler(repo, processor, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   40 * time.Millisecond,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.True(t, repo.failWhileLocked)
	assert.False(t, repo.failContextCanceled)
}

func TestProcessPreCanceledCallerRemainsRetryable(t *testing.T) {
	repo := newFakeRepository()
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := newTestHandler(repo, &fakeProcessor{}, &fakeFollowUp{}).Process(ctx, delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.ErrorIs(t, err, context.Canceled)
	assert.Zero(t, repo.failCalls)
}

func TestProcessEqualCallerAndJobDeadlinesAreJobOwned(t *testing.T) {
	deadline := time.Now().Add(40 * time.Millisecond)
	ctx, cancel := context.WithDeadline(context.Background(), deadline)
	defer cancel()
	repo := newFakeRepository()
	started := deadline.Add(-time.Second)
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	handler := NewHandler(repo, &fakeProcessor{waitForContext: true}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   time.Second,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.True(t, repo.failWhileLocked)
}

func TestProcessDeadlineDuringCompleteTerminalizesTimeout(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	repo.completeWaitForContext = true
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   40 * time.Millisecond,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(context.Background(), delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.True(t, repo.failWhileLocked)
}

func TestProcessCompleteJobDeadlineBeforeLaterCallerCancellationTerminalizesTimeout(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	repo.completeWaitForContext = true
	repo.completeAfterContextDone = cancel
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   40 * time.Millisecond,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.True(t, repo.failWhileLocked)
	assert.False(t, repo.failContextCanceled)
}

func TestProcessCompleteCallerCancellationBeforeJobDeadlineRemainsRetryable(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	repo.completeWaitForContext = true
	repo.completeBeforeWait = cancel
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   time.Second,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, context.Canceled)
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.failCalls)
}

func TestProcessCompleteEarlierCallerDeadlineRemainsRetryable(t *testing.T) {
	repo := newFakeRepository()
	started := time.Now()
	repo.latest.CreatedAt = started
	repo.started.CreatedAt = started
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Millisecond)
	defer cancel()
	repo.completeWaitForContext = true
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   time.Second,
		FinalizationTimeout: time.Second,
		Now:                 time.Now,
	})

	err := handler.Process(ctx, delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, context.DeadlineExceeded)
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.failCalls)
}

func TestProcessDeadlineAfterCompressBeforeCompleteTerminalizesTimeout(t *testing.T) {
	started := fixedNow
	deadline := started.Add(15 * time.Minute)
	clock := &fakeClock{times: []time.Time{
		started,
		deadline.Add(time.Nanosecond),
	}}
	repo := newFakeRepository()
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   15 * time.Minute,
		FinalizationTimeout: time.Second,
		Now:                 clock.Now,
	})

	err := handler.Process(context.Background(), delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
	assert.Zero(t, repo.completeCalls)
}

func TestProcessCompleteDeadlineAfterLastPrecheckTerminalizesTimeout(t *testing.T) {
	started := fixedNow
	deadline := started.Add(15 * time.Minute)
	clock := &fakeClock{times: []time.Time{
		started,
		started,
		deadline.Add(time.Nanosecond),
	}}
	repo := newFakeRepository()
	repo.completeErr = context.DeadlineExceeded
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   15 * time.Minute,
		FinalizationTimeout: time.Second,
		Now:                 clock.Now,
	})

	err := handler.Process(context.Background(), delivery(41))

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionTimeout, repo.failureCode)
}

func TestProcessUnrelatedCompleteFailureAfterDeadlineRemainsRetryable(t *testing.T) {
	started := fixedNow
	deadline := started.Add(15 * time.Minute)
	clock := &fakeClock{times: []time.Time{
		started,
		started,
		deadline.Add(time.Nanosecond),
	}}
	persistenceCause := errors.New("database commit failed")
	repo := newFakeRepository()
	repo.completeErr = persistenceCause
	handler := NewHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   15 * time.Minute,
		FinalizationTimeout: time.Second,
		Now:                 clock.Now,
	})

	err := handler.Process(context.Background(), delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, persistenceCause)
	assert.Zero(t, repo.failCalls)
}

func TestProcessConfirmedCompleteWinsOverReturnedDeadlineError(t *testing.T) {
	repo := newFakeRepository()
	repo.completeJob = terminalJob(store.StatusCompleted)
	repo.completeErr = context.DeadlineExceeded
	followUp := &fakeFollowUp{}

	err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, followUp).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	assert.Equal(t, 1, followUp.calls)
	assert.Zero(t, repo.failCalls)
}

func TestProcessPersistsCompletedAndSkippedBeforeFollowUp(t *testing.T) {
	tests := []struct {
		name   string
		result store.CompressionResult
	}{
		{name: "completed", result: completedResult()},
		{name: "skipped", result: store.CompressionResult{Status: store.StatusSkipped}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			processor := &fakeProcessor{result: tt.result}
			followUp := &fakeFollowUp{repo: repo}

			err := newTestHandler(repo, processor, followUp).Process(
				context.Background(),
				delivery(41),
			)

			require.NoError(t, err)
			assert.Equal(t, tt.result.Status, repo.completed.Status)
			assert.Equal(t, 1, followUp.calls)
			assert.True(t, followUp.sawTerminal)
		})
	}
}

func TestProcessDeterministicFailurePersistsSafeCodeWithBoundedFinalizationContext(t *testing.T) {
	processorCause := errors.New("corrupt document at /sensitive/path.pdf")
	repo := newFakeRepository()
	processor := &fakeProcessor{
		err: NewDeterministicFailure(store.FailureCodeUnsupportedDocument, processorCause),
	}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeUnsupportedDocument, repo.failureCode)
	assert.False(t, repo.failContextCanceled)
	assert.Zero(t, repo.completeCalls)
}

func TestProcessTransientFailureReturnsSafeRetryableCause(t *testing.T) {
	processorCause := errors.New("temporary S3 response from /sensitive/path.pdf")
	repo := newFakeRepository()
	processor := &fakeProcessor{
		err: NewRetryableFailure(store.FailureCodeS3UploadFailed, processorCause),
	}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeS3UploadFailed), err.Error())
	assert.NotContains(t, err.Error(), "sensitive")
	assert.ErrorIs(t, err, processorCause)
	assert.True(t, IsRetryable(err))
	assert.Zero(t, repo.failCalls)
	assert.Zero(t, repo.completeCalls)
}

func TestProcessPanicTerminalizesWhileLockHeld(t *testing.T) {
	panicCause := errors.New("panic containing /sensitive/path.pdf")
	repo := newFakeRepository()
	processor := &fakeProcessor{panicValue: panicCause}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	assert.Equal(t, store.FailureCodeCompressionPanic, repo.failureCode)
	assert.True(t, repo.failWhileLocked)
}

func TestProcessTerminalPersistenceFailureIsSafeRetryableAndInspectible(t *testing.T) {
	processorCause := errors.New("processor detail")
	persistenceCause := errors.New("database detail at secret.internal")
	repo := newFakeRepository()
	repo.failErr = persistenceCause
	processor := &fakeProcessor{
		err: NewDeterministicFailure(store.FailureCodeUnsupportedDocument, processorCause),
	}

	err := newTestHandler(repo, processor, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.NotContains(t, err.Error(), "secret.internal")
	assert.ErrorIs(t, err, processorCause)
	assert.ErrorIs(t, err, persistenceCause)
	assert.True(t, IsRetryable(err))
}

func TestProcessFinalizationTimeoutIsSafeRetryable(t *testing.T) {
	repo := newFakeRepository()
	repo.failWaitForContext = true
	handler := NewHandler(
		repo,
		&fakeProcessor{err: NewDeterministicFailure(store.FailureCodeUnsupportedDocument, nil)},
		&fakeFollowUp{},
		Options{
			Workload:            config.WorkloadNormal,
			ProcessingTimeout:   time.Minute,
			FinalizationTimeout: 40 * time.Millisecond,
			Now:                 time.Now,
		},
	)

	err := handler.Process(context.Background(), delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, context.DeadlineExceeded)
	assert.True(t, IsRetryable(err))
}

func TestProcessFinalizationPanicIsSafeRetryable(t *testing.T) {
	panicCause := errors.New("finalization panic detail")
	repo := newFakeRepository()
	repo.failPanic = panicCause

	err := newTestHandler(
		repo,
		&fakeProcessor{err: NewDeterministicFailure(store.FailureCodeUnsupportedDocument, nil)},
		&fakeFollowUp{},
	).Process(context.Background(), delivery(41))

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, panicCause)
	assert.True(t, IsRetryable(err))
}

func TestProcessCompletionPersistenceFailureDoesNotFollowUp(t *testing.T) {
	persistenceCause := errors.New("commit failed")
	repo := newFakeRepository()
	repo.completeErr = persistenceCause
	followUp := &fakeFollowUp{}

	err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, followUp).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.ErrorIs(t, err, persistenceCause)
	assert.Zero(t, followUp.calls)
}

func TestProcessRequiresConfirmedVersionThree(t *testing.T) {
	repo := newFakeRepository()
	repo.completeJob = store.Job{JobID: 41, Version: 2, Status: store.StatusStarted}

	err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
	assert.True(t, IsRetryable(err))
}

func TestProcessRejectsUnconfirmedCompleteConflictWinner(t *testing.T) {
	tests := []struct {
		name string
		job  store.Job
	}{
		{name: "unknown status", job: terminalJob(store.StatusStarted)},
		{name: "wrong job identifier", job: store.Job{JobID: 99, Version: 3, Status: store.StatusCompleted}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.completeJob = tt.job
			followUp := &fakeFollowUp{}

			err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, followUp).Process(
				context.Background(),
				delivery(41),
			)

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
			assert.Zero(t, followUp.calls)
		})
	}
}

func TestProcessRejectsUnconfirmedFailConflictWinner(t *testing.T) {
	tests := []struct {
		name string
		job  store.Job
	}{
		{name: "unknown status", job: terminalJob(store.StatusStarted)},
		{name: "wrong job identifier", job: store.Job{JobID: 99, Version: 3, Status: store.StatusError}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.failJob = tt.job
			followUp := &fakeFollowUp{}

			err := newTestHandler(
				repo,
				&fakeProcessor{err: NewDeterministicFailure(store.FailureCodeUnsupportedDocument, nil)},
				followUp,
			).Process(context.Background(), delivery(41))

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
			assert.Zero(t, followUp.calls)
		})
	}
}

func TestProcessCompletionConflictWinnerErrorDoesNotFollowUp(t *testing.T) {
	repo := newFakeRepository()
	repo.completeJob = terminalJob(store.StatusError)
	followUp := &fakeFollowUp{}

	err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, followUp).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	assert.Zero(t, followUp.calls)
}

func TestProcessBestEffortFollowUpPanicDoesNotUndoTerminalState(t *testing.T) {
	repo := newFakeRepository()
	followUp := &fakeFollowUp{panicValue: errors.New("follow-up panic")}

	err := newTestHandler(repo, &fakeProcessor{result: completedResult()}, followUp).Process(
		context.Background(),
		delivery(41),
	)

	require.NoError(t, err)
	assert.Equal(t, 1, followUp.calls)
	assert.Equal(t, store.StatusCompleted, repo.completed.Status)
}

func TestProcessPanicBeforeLockAcquisitionReturnsSafeRetryableFailure(t *testing.T) {
	panicCause := errors.New("repository panic with credentials")
	repo := newFakeRepository()
	repo.lockPanic = panicCause

	err := newTestHandler(repo, &fakeProcessor{}, &fakeFollowUp{}).Process(
		context.Background(),
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeCompressionPanic), err.Error())
	assert.ErrorIs(t, err, panicCause)
	assert.True(t, IsRetryable(err))
}

func TestProcessNilContextReturnsSafeRetryableFailure(t *testing.T) {
	err := newTestHandler(newFakeRepository(), &fakeProcessor{}, &fakeFollowUp{}).Process(
		nil,
		delivery(41),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
	assert.True(t, IsRetryable(err))
}

func TestProcessRejectsNilProcessorBeforeLock(t *testing.T) {
	tests := []struct {
		name      string
		processor Processor
	}{
		{name: "nil", processor: nil},
		{name: "typed nil", processor: (*fakeProcessor)(nil)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()

			err := newTestHandler(repo, tt.processor, &fakeFollowUp{}).Process(
				context.Background(),
				delivery(41),
			)

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
			assert.True(t, IsRetryable(err))
			assert.Zero(t, repo.lockCalls)
			assert.Zero(t, repo.failCalls)
		})
	}
}

func TestProcessRejectsNilRepositoryBeforeLock(t *testing.T) {
	tests := []struct {
		name       string
		repository Repository
	}{
		{name: "nil", repository: nil},
		{name: "typed nil", repository: (*fakeRepository)(nil)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := newTestHandler(tt.repository, &fakeProcessor{}, &fakeFollowUp{}).Process(
				context.Background(),
				delivery(41),
			)

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
			assert.True(t, IsRetryable(err))
		})
	}
}

func TestProcessNilFollowUpIsNoOpAfterCompletion(t *testing.T) {
	tests := []struct {
		name     string
		followUp FollowUp
	}{
		{name: "nil", followUp: nil},
		{name: "typed nil", followUp: (*fakeFollowUp)(nil)},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := newTestHandler(
				newFakeRepository(),
				&fakeProcessor{result: completedResult()},
				tt.followUp,
			).Process(context.Background(), delivery(41))

			require.NoError(t, err)
		})
	}
}

func TestProcessPanicCauseRemainsSafelyInspectable(t *testing.T) {
	panicErr := errors.New("panic error with /sensitive/path.pdf")
	tests := []struct {
		name       string
		panicValue any
		wantError  error
		wantValue  any
	}{
		{name: "error panic", panicValue: panicErr, wantError: panicErr, wantValue: panicErr},
		{name: "non-error panic", panicValue: "panic text /sensitive/path.pdf", wantValue: "panic text /sensitive/path.pdf"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			repo := newFakeRepository()
			repo.failErr = errors.New("terminal persistence failed")

			err := newTestHandler(
				repo,
				&fakeProcessor{panicValue: tt.panicValue},
				&fakeFollowUp{},
			).Process(context.Background(), delivery(41))

			require.Error(t, err)
			assert.Equal(t, string(store.FailureCodeTerminalStatePersistFailed), err.Error())
			assert.NotContains(t, err.Error(), "sensitive")
			if tt.wantError != nil {
				assert.ErrorIs(t, err, tt.wantError)
			}
			var panicCause interface{ PanicValue() any }
			require.ErrorAs(t, err, &panicCause)
			assert.Equal(t, tt.wantValue, panicCause.PanicValue())
			assert.Equal(t, "panic recovered", panicCause.(error).Error())
		})
	}
}

func TestFailureUsesBoundedCodeAndPreservesCause(t *testing.T) {
	cause := errors.New("secret path /document.pdf")
	err := NewRetryableFailure(store.FailureCode("not-approved: "+cause.Error()), cause)

	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.NotContains(t, err.Error(), "document.pdf")
	assert.ErrorIs(t, err, cause)
	assert.True(t, IsRetryable(err))
	assert.False(t, IsDeterministic(err))
}

func TestDirectFailureConstructionCannotExposeUnapprovedCode(t *testing.T) {
	cause := errors.New("secret path /document.pdf")
	err := &Failure{
		Code:      "not-approved: " + cause.Error(),
		Retryable: true,
		cause:     cause,
	}

	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.NotContains(t, err.Error(), "document.pdf")
	assert.ErrorIs(t, err, cause)
}

func TestTypedNilFailureIsConservativelyRetryable(t *testing.T) {
	var failure *Failure
	var err error = failure

	assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
	assert.True(t, IsRetryable(err))
	assert.False(t, IsDeterministic(err))

	retried := retryFrom(err, store.FailureCodeS3UploadFailed)
	require.Error(t, retried)
	assert.Equal(t, string(store.FailureCodeInvalidMessage), retried.Error())
	assert.True(t, IsRetryable(retried))
}

type fakeRepository struct {
	latest                   store.Job
	latestFound              bool
	latestErr                error
	started                  store.Job
	ensureStartedErr         error
	completeJob              store.Job
	completeErr              error
	completeWaitForContext   bool
	completeBeforeWait       func()
	completeAfterContextDone func()
	failJob                  store.Job
	failErr                  error
	failPanic                any
	failWaitForContext       bool
	contended                bool
	lockErr                  error
	lockPanic                any
	skipCallback             bool
	inLock                   bool
	lockCalls                int
	latestCalls              int
	ensureStartedCalls       int
	completeCalls            int
	failCalls                int
	failureCode              store.FailureCode
	failWhileLocked          bool
	failContextCanceled      bool
	completed                store.CompressionResult
}

func newFakeRepository() *fakeRepository {
	return &fakeRepository{
		latest:      startedJob(config.WorkloadNormal),
		latestFound: true,
		started:     startedJob(config.WorkloadNormal),
	}
}

func (r *fakeRepository) WithinJobLock(
	ctx context.Context,
	_ int,
	callback func(context.Context) error,
) (bool, error) {
	r.lockCalls++
	if r.lockPanic != nil {
		panic(r.lockPanic)
	}
	if r.lockErr != nil {
		return false, r.lockErr
	}
	if r.contended {
		return false, nil
	}
	if r.skipCallback {
		return true, nil
	}
	r.inLock = true
	defer func() { r.inLock = false }()
	return true, callback(ctx)
}

func (r *fakeRepository) Latest(context.Context, int) (store.Job, bool, error) {
	r.latestCalls++
	return r.latest, r.latestFound, r.latestErr
}

func (r *fakeRepository) EnsureStarted(
	context.Context,
	models.CompressionProducerMessage,
	config.Workload,
) (store.Job, error) {
	r.ensureStartedCalls++
	return r.started, r.ensureStartedErr
}

func (r *fakeRepository) Complete(
	ctx context.Context,
	_ models.CompressionProducerMessage,
	result store.CompressionResult,
) (store.Job, error) {
	r.completeCalls++
	r.completed = result
	if r.completeWaitForContext {
		if r.completeBeforeWait != nil {
			r.completeBeforeWait()
		}
		<-ctx.Done()
		if r.completeAfterContextDone != nil {
			r.completeAfterContextDone()
		}
		return r.completeJob, ctx.Err()
	}
	if r.completeErr != nil {
		return r.completeJob, r.completeErr
	}
	if err := ctx.Err(); err != nil {
		return r.completeJob, err
	}
	if r.completeJob.Version != 0 {
		return r.completeJob, nil
	}
	return terminalJob(result.Status), nil
}

func (r *fakeRepository) Fail(
	ctx context.Context,
	_ int,
	code store.FailureCode,
) (store.Job, error) {
	r.failCalls++
	r.failureCode = code
	r.failWhileLocked = r.inLock
	r.failContextCanceled = ctx.Err() != nil
	if r.failPanic != nil {
		panic(r.failPanic)
	}
	if r.failWaitForContext {
		<-ctx.Done()
		return r.failJob, ctx.Err()
	}
	if r.failErr != nil {
		return r.failJob, r.failErr
	}
	if err := ctx.Err(); err != nil {
		return r.failJob, err
	}
	if r.failJob.Version != 0 {
		return r.failJob, nil
	}
	return terminalJob(store.StatusError), nil
}

type fakeProcessor struct {
	result           store.CompressionResult
	err              error
	panicValue       any
	after            func()
	waitForContext   bool
	afterContextDone func()
	calls            int
	deadline         *time.Time
}

func (p *fakeProcessor) Compress(
	ctx context.Context,
	_ models.CompressionProducerMessage,
) (store.CompressionResult, error) {
	p.calls++
	if deadline, ok := ctx.Deadline(); ok {
		p.deadline = &deadline
	}
	if p.after != nil {
		p.after()
	}
	if p.panicValue != nil {
		panic(p.panicValue)
	}
	if p.err != nil {
		return p.result, p.err
	}
	if p.waitForContext {
		<-ctx.Done()
		if p.afterContextDone != nil {
			p.afterContextDone()
		}
		return p.result, ctx.Err()
	}
	if err := ctx.Err(); err != nil {
		return p.result, err
	}
	return p.result, nil
}

type fakeClock struct {
	times []time.Time
	calls int
}

func (c *fakeClock) Now() time.Time {
	if len(c.times) == 0 {
		return time.Now()
	}
	index := c.calls
	if index >= len(c.times) {
		index = len(c.times) - 1
	}
	c.calls++
	return c.times[index]
}

type fakeFollowUp struct {
	repo        *fakeRepository
	panicValue  any
	calls       int
	sawTerminal bool
}

func (f *fakeFollowUp) AfterTerminal(
	context.Context,
	models.CompressionProducerMessage,
	store.CompressionResult,
) {
	f.calls++
	if f.repo != nil {
		f.sawTerminal = f.repo.completeCalls == 1 && f.repo.completed.Status != ""
	}
	if f.panicValue != nil {
		panic(f.panicValue)
	}
}

func newTestHandler(repo Repository, processor Processor, followUp FollowUp) *Handler {
	return NewHandler(repo, processor, followUp, Options{
		Workload:            config.WorkloadNormal,
		ProcessingTimeout:   15 * time.Minute,
		FinalizationTimeout: 10 * time.Second,
		Now:                 func() time.Time { return fixedNow },
	})
}

func delivery(jobID int) Delivery {
	return Delivery{
		EventID:       "event-1",
		CorrelationID: "correlation-1",
		StreamID:      "stream-1",
		Workload:      config.WorkloadNormal,
		Message: models.CompressionProducerMessage{
			JobID: jobID,
		},
	}
}

func startedJob(workload config.Workload) store.Job {
	return store.Job{
		JobID:         41,
		Version:       2,
		Status:        store.StatusStarted,
		Workload:      workload,
		WorkloadKnown: true,
		CreatedAt:     fixedNow,
	}
}

func terminalJob(status string) store.Job {
	return store.Job{
		JobID:         41,
		Version:       3,
		Status:        status,
		Workload:      config.WorkloadNormal,
		WorkloadKnown: true,
		CreatedAt:     fixedNow,
	}
}

func completedResult() store.CompressionResult {
	return store.CompressionResult{
		Status:         store.StatusCompleted,
		CompressedPath: "bucket/documentCOMPRESSED.pdf",
		CompressedSize: 1234,
		Extension:      ".pdf",
	}
}
