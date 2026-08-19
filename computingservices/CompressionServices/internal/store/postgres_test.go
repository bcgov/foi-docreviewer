package store

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"errors"
	"io"
	"strings"
	"sync"
	"testing"
	"time"

	"compressionservices/internal/config"
	"compressionservices/models"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

var fixedCreatedAt = time.Date(2026, 8, 18, 12, 0, 0, 0, time.UTC)

func TestWithinJobLockReleasesLock(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(true))
	mock.ExpectQuery("pg_advisory_unlock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"unlocked"}).AddRow(true))

	acquired, err := New(db, Options{OperationTimeout: 10 * time.Second}).WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error { return nil },
	)

	require.NoError(t, err)
	assert.True(t, acquired)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestWithinJobLockContentionDoesNotInvokeCallbackOrUnlock(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(false))
	called := false

	acquired, err := New(db, Options{OperationTimeout: time.Second}).WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error {
			called = true
			return nil
		},
	)

	require.NoError(t, err)
	assert.False(t, acquired)
	assert.False(t, called)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestWithinJobLockDoesNotCapCallbackAtOperationTimeout(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(true))
	mock.ExpectQuery("pg_advisory_unlock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"unlocked"}).AddRow(true))

	acquired, err := New(db, Options{OperationTimeout: 5 * time.Millisecond}).WithinJobLock(
		context.Background(),
		41,
		func(ctx context.Context) error {
			timer := time.NewTimer(15 * time.Millisecond)
			defer timer.Stop()
			select {
			case <-ctx.Done():
				return ctx.Err()
			case <-timer.C:
				return nil
			}
		},
	)

	require.NoError(t, err)
	assert.True(t, acquired)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestWithinJobLockPropagatesCallerCancellationToCallback(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(true))
	mock.ExpectQuery("pg_advisory_unlock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"unlocked"}).AddRow(true))
	ctx, cancel := context.WithCancel(context.Background())

	acquired, err := New(db, Options{OperationTimeout: time.Second}).WithinJobLock(
		ctx,
		41,
		func(callbackCtx context.Context) error {
			cancel()
			<-callbackCtx.Done()
			return callbackCtx.Err()
		},
	)

	assert.True(t, acquired)
	assert.ErrorIs(t, err, context.Canceled)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestWithinJobLockJoinsCallbackAndUnlockErrors(t *testing.T) {
	db, mock := newMock(t)
	callbackErr := errors.New("callback failed")
	unlockErr := errors.New("unlock failed")
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(true))
	mock.ExpectQuery("pg_advisory_unlock").
		WithArgs(int32(5199), 41).
		WillReturnError(unlockErr)

	acquired, err := New(db, Options{OperationTimeout: time.Second}).WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error { return callbackErr },
	)

	assert.True(t, acquired)
	assert.ErrorIs(t, err, callbackErr)
	assert.ErrorIs(t, err, unlockErr)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestWithinJobLockRetiresSessionAfterUnlockFailure(t *testing.T) {
	state := &retirementDriverState{}
	db := sql.OpenDB(retirementConnector{state: state})
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	t.Cleanup(func() { require.NoError(t, db.Close()) })
	repository := New(db, Options{OperationTimeout: time.Second})

	acquired, err := repository.WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error { return nil },
	)

	assert.True(t, acquired)
	require.Error(t, err)
	assert.Equal(t, 1, state.closeCount())

	acquired, err = repository.WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error { return nil },
	)

	require.NoError(t, err)
	assert.True(t, acquired)
	assert.Equal(t, 2, state.openCount())
}

func TestWithinJobLockRetiresSessionWhenUnlockReturnsFalse(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery("pg_try_advisory_lock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"locked"}).AddRow(true))
	mock.ExpectQuery("pg_advisory_unlock").
		WithArgs(int32(5199), 41).
		WillReturnRows(sqlmock.NewRows([]string{"unlocked"}).AddRow(false))

	acquired, err := New(db, Options{OperationTimeout: time.Second}).WithinJobLock(
		context.Background(),
		41,
		func(context.Context) error { return nil },
	)

	assert.True(t, acquired)
	assert.ErrorIs(t, err, ErrLockNotReleased)
	assert.Zero(t, db.Stats().OpenConnections)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestLatestReadsVersionThree(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT compressionjobid, version, status, workload, createdat`).
		WithArgs(41).
		WillReturnRows(jobRows().AddRow(41, 3, StatusCompleted, "normal", fixedCreatedAt))

	job, found, err := New(db, Options{OperationTimeout: time.Second}).Latest(context.Background(), 41)

	require.NoError(t, err)
	assert.True(t, found)
	assert.Equal(t, Job{
		JobID:         41,
		Version:       3,
		Status:        StatusCompleted,
		Workload:      config.WorkloadNormal,
		WorkloadKnown: true,
		CreatedAt:     fixedCreatedAt,
	}, job)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestLatestReturnsNotFoundExplicitly(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT compressionjobid, version, status, workload, createdat`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)

	job, found, err := New(db, Options{OperationTimeout: time.Second}).Latest(context.Background(), 41)

	require.NoError(t, err)
	assert.False(t, found)
	assert.Equal(t, Job{}, job)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestLatestPreservesUnknownWorkload(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT compressionjobid, version, status, workload, createdat`).
		WithArgs(41).
		WillReturnRows(jobRows().AddRow(41, 1, StatusPushedToStream, nil, fixedCreatedAt))

	job, found, err := New(db, Options{OperationTimeout: time.Second}).Latest(context.Background(), 41)

	require.NoError(t, err)
	assert.True(t, found)
	assert.False(t, job.WorkloadKnown)
	assert.Empty(t, job.Workload)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestEnsureStartedWritesWorkloadAndRereadsAuthoritativeRow(t *testing.T) {
	db, mock := newMock(t)
	msg := testMessage()
	msg.MinistryRequestID = 999
	msg.Batch = "forged-batch"
	msg.Trigger = "forged-trigger"
	msg.Filename = "forged.pdf"
	msg.DocumentMasterID = 998
	mock.ExpectExec(`(?s)INSERT INTO public\."CompressionJob".*SELECT compressionjobid, 2, ministryrequestid, batch, trigger, filename, \$3, documentmasterid, COALESCE\(workload, \$2\).*WHERE compressionjobid = \$1 AND version = 1`).
		WithArgs(41, config.WorkloadLarge, StatusStarted).
		WillReturnResult(sqlmock.NewResult(0, 0))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 2`).
		WithArgs(41).
		WillReturnRows(jobRows().AddRow(41, 2, StatusStarted, "normal", fixedCreatedAt))

	job, err := New(db, Options{OperationTimeout: time.Second}).EnsureStarted(
		context.Background(),
		msg,
		config.WorkloadLarge,
	)

	require.NoError(t, err)
	assert.Equal(t, config.WorkloadNormal, job.Workload)
	assert.True(t, job.WorkloadKnown)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompletePersistsSuccessAndDocumentUpdatesAtomically(t *testing.T) {
	db, mock := newMock(t)
	msg := testMessage()
	result := CompressionResult{
		Status:         StatusCompleted,
		CompressedPath: "bucket/documentCOMPRESSED.pdf",
		CompressedSize: 1234,
		Extension:      ".pdf",
	}
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusCompleted).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusCompleted, "large", fixedCreatedAt, 501, 601))
	mock.ExpectExec(`(?s)UPDATE "DocumentAttributes".*cj\.compressionjobid = \$3.*cj\.version = 3.*cj\.status = \$4`).
		WithArgs(501, sql.NullInt64{Int64: 1234, Valid: true}, 41, StatusCompleted).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec(`(?s)UPDATE "DocumentMaster".*cj\.compressionjobid = \$5.*cj\.version = 3.*cj\.status = \$4`).
		WithArgs(501, sql.NullString{String: result.CompressedPath, Valid: true}, 601, StatusCompleted, 41).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectCommit()

	job, err := New(db, Options{OperationTimeout: time.Second}).Complete(context.Background(), msg, result)

	require.NoError(t, err)
	assert.Equal(t, StatusCompleted, job.Status)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompletePersistsSkippedNullDocumentValuesAtomically(t *testing.T) {
	db, mock := newMock(t)
	msg := testMessage()
	result := CompressionResult{Status: StatusSkipped}
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusSkipped).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusSkipped, "normal", fixedCreatedAt, 502, 602))
	mock.ExpectExec(`(?s)UPDATE "DocumentAttributes".*cj\.compressionjobid = \$3.*cj\.version = 3.*cj\.status = \$4`).
		WithArgs(502, sql.NullInt64{Valid: false}, 41, StatusSkipped).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec(`(?s)UPDATE "DocumentMaster".*cj\.compressionjobid = \$5.*cj\.version = 3.*cj\.status = \$4`).
		WithArgs(502, sql.NullString{Valid: false}, 602, StatusSkipped, 41).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectCommit()

	job, err := New(db, Options{OperationTimeout: time.Second}).Complete(context.Background(), msg, result)

	require.NoError(t, err)
	assert.Equal(t, StatusSkipped, job.Status)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteExistingErrorDoesNotApplySuccessUpdates(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusError, "normal", fixedCreatedAt, 501, 601))
	mock.ExpectCommit()

	job, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusCompleted},
	)

	require.NoError(t, err)
	assert.Equal(t, StatusError, job.Status)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteConflictWinnerErrorDoesNotApplySuccessUpdates(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusCompleted).
		WillReturnResult(sqlmock.NewResult(0, 0))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusError, "normal", fixedCreatedAt, 501, 601))
	mock.ExpectCommit()

	job, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusCompleted},
	)

	require.NoError(t, err)
	assert.Equal(t, StatusError, job.Status)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteRejectsNonSuccessStatus(t *testing.T) {
	db, mock := newMock(t)

	_, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusError},
	)

	assert.ErrorIs(t, err, ErrInvalidTerminalStatus)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteJoinsInsertAndRollbackErrors(t *testing.T) {
	db, mock := newMock(t)
	insertErr := errors.New("insert failed")
	rollbackErr := errors.New("rollback failed")
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusCompleted).
		WillReturnError(insertErr)
	mock.ExpectRollback().WillReturnError(rollbackErr)

	_, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusCompleted},
	)

	assert.ErrorIs(t, err, insertErr)
	assert.ErrorIs(t, err, rollbackErr)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteRollsBackWhenConflictWinnerRereadFails(t *testing.T) {
	db, mock := newMock(t)
	rereadErr := errors.New("reread failed")
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusCompleted).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(rereadErr)
	mock.ExpectRollback()

	_, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusCompleted},
	)

	assert.ErrorIs(t, err, rereadErr)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteRollsBackWhenDocumentUpdateFails(t *testing.T) {
	db, mock := newMock(t)
	updateErr := errors.New("attribute update failed")
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusCompleted).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusCompleted, "normal", fixedCreatedAt, 501, 601))
	mock.ExpectExec(`UPDATE "DocumentAttributes"`).
		WithArgs(501, sql.NullInt64{Valid: true}, 41, StatusCompleted).
		WillReturnError(updateErr)
	mock.ExpectRollback()

	_, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusCompleted},
	)

	assert.ErrorIs(t, err, updateErr)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCompleteReturnsCommitFailure(t *testing.T) {
	db, mock := newMock(t)
	commitErr := errors.New("commit failed")
	mock.ExpectBegin()
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusSkipped).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(storedJobRows().AddRow(41, 3, StatusSkipped, "normal", fixedCreatedAt, 501, 601))
	mock.ExpectExec(`UPDATE "DocumentAttributes"`).
		WithArgs(501, sql.NullInt64{Valid: false}, 41, StatusSkipped).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectExec(`UPDATE "DocumentMaster"`).
		WithArgs(501, sql.NullString{Valid: false}, 601, StatusSkipped, 41).
		WillReturnResult(sqlmock.NewResult(0, 1))
	mock.ExpectCommit().WillReturnError(commitErr)

	_, err := New(db, Options{OperationTimeout: time.Second}).Complete(
		context.Background(),
		testMessage(),
		CompressionResult{Status: StatusSkipped},
	)

	assert.ErrorIs(t, err, commitErr)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestFailPersistsOnlySafeCodeAndRereadsConflictWinner(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WithArgs(41, StatusError, FailureCodeWorkloadMismatch).
		WillReturnResult(sqlmock.NewResult(0, 0))
	mock.ExpectQuery(`WHERE compressionjobid = \$1 AND version = 3`).
		WithArgs(41).
		WillReturnRows(jobRows().AddRow(41, 3, StatusCompleted, "normal", fixedCreatedAt))

	job, err := New(db, Options{OperationTimeout: time.Second}).Fail(
		context.Background(),
		41,
		FailureCodeWorkloadMismatch,
	)

	require.NoError(t, err)
	assert.Equal(t, StatusCompleted, job.Status)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestFailRejectsUnknownOrUnboundedMessage(t *testing.T) {
	db, mock := newMock(t)

	_, err := New(db, Options{OperationTimeout: time.Second}).Fail(
		context.Background(),
		41,
		FailureCode("raw database error containing a path /secret/document.pdf"),
	)

	assert.ErrorIs(t, err, ErrInvalidFailureCode)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestListStaleUsesWorkloadThresholdsAndBoundedDeterministicOrder(t *testing.T) {
	db, mock := newMock(t)
	thresholds := Thresholds{
		Normal:  20 * time.Minute,
		Large:   75 * time.Minute,
		Unknown: 80 * time.Minute,
	}
	mock.ExpectQuery(`(?s)DISTINCT ON \(compressionjobid\).*version IN \(1, 2\).*CASE workload\s+WHEN 'normal' THEN make_interval\(secs => \$1\)\s+WHEN 'large' THEN make_interval\(secs => \$2\)\s+ELSE make_interval\(secs => \$3\)\s+END.*ORDER BY createdat, compressionjobid.*LIMIT \$4`).
		WithArgs(thresholds.Normal.Seconds(), thresholds.Large.Seconds(), thresholds.Unknown.Seconds(), 3).
		WillReturnRows(jobRows().
			AddRow(1, 2, StatusStarted, "normal", fixedCreatedAt).
			AddRow(2, 1, StatusPushedToStream, "large", fixedCreatedAt.Add(time.Second)).
			AddRow(3, 1, StatusPushedToStream, nil, fixedCreatedAt.Add(2*time.Second)))

	jobs, err := New(db, Options{OperationTimeout: time.Second}).ListStale(
		context.Background(),
		thresholds,
		3,
	)

	require.NoError(t, err)
	require.Len(t, jobs, 3)
	assert.Equal(t, []int{1, 2, 3}, []int{jobs[0].JobID, jobs[1].JobID, jobs[2].JobID})
	assert.False(t, jobs[2].WorkloadKnown)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCredentialsUsesDocumentPathMapperAndSharedPool(t *testing.T) {
	t.Setenv("COMPRESSION_S3_ENV", "DEV")
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT attributes\s+FROM public\."DocumentPathMapper"`).
		WithArgs("citz-dev-e").
		WillReturnRows(sqlmock.NewRows([]string{"attributes"}).AddRow(`{"s3accesskey":"access","s3secretkey":"secret"}`))

	credentials, bucket, err := New(db, Options{OperationTimeout: time.Second}).Credentials(
		context.Background(),
		"CITZ",
	)

	require.NoError(t, err)
	assert.Equal(t, "citz-dev-e", bucket)
	assert.Equal(t, "access", credentials.S3AccessKey)
	assert.Equal(t, "secret", credentials.S3SecretKey)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCredentialsHandlesNoRowsSafely(t *testing.T) {
	t.Setenv("COMPRESSION_S3_ENV", "dev")
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT attributes\s+FROM public\."DocumentPathMapper"`).
		WithArgs("citz-dev-e").
		WillReturnError(sql.ErrNoRows)

	_, _, err := New(db, Options{OperationTimeout: time.Second}).Credentials(context.Background(), "CITZ")

	assert.ErrorIs(t, err, ErrCredentialsNotFound)
	assert.NotContains(t, err.Error(), "citz-dev-e")
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCredentialsRejectsNullAttributesSafely(t *testing.T) {
	t.Setenv("COMPRESSION_S3_ENV", "dev")
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT attributes\s+FROM public\."DocumentPathMapper"`).
		WithArgs("citz-dev-e").
		WillReturnRows(sqlmock.NewRows([]string{"attributes"}).AddRow(nil))

	_, _, err := New(db, Options{OperationTimeout: time.Second}).Credentials(context.Background(), "CITZ")

	assert.ErrorIs(t, err, ErrCredentialsInvalid)
	assert.Equal(t, "credentials_invalid", err.Error())
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestCredentialsRejectsMalformedJSONSafely(t *testing.T) {
	t.Setenv("COMPRESSION_S3_ENV", "dev")
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT attributes\s+FROM public\."DocumentPathMapper"`).
		WithArgs("citz-dev-e").
		WillReturnRows(sqlmock.NewRows([]string{"attributes"}).AddRow(`{"s3accesskey":`))

	_, _, err := New(db, Options{OperationTimeout: time.Second}).Credentials(context.Background(), "CITZ")

	assert.ErrorIs(t, err, ErrCredentialsInvalid)
	assert.Equal(t, "credentials_invalid", err.Error())
	assert.NotContains(t, err.Error(), "s3accesskey")
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestEnsureOCRStartedUsesExistingConflictSemantics(t *testing.T) {
	db, mock := newMock(t)
	msg := testMessage()
	mock.ExpectExec(`INSERT INTO public\."OCRActiveMQJob"`).
		WithArgs(41, 1, 72, "batch-1", "recordupload", "document.pdf", StatusPushedToStream, 93).
		WillReturnResult(sqlmock.NewResult(0, 0))

	jobID, err := New(db, Options{OperationTimeout: time.Second}).EnsureOCRStarted(context.Background(), msg)

	require.NoError(t, err)
	assert.Equal(t, 41, jobID)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestUpdateRedactionReadyUsesExistingLatestCompletedSemantics(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectExec(`(?s)UPDATE "DocumentMaster" dm.*DISTINCT ON \(documentmasterid\).*sq\.status = 'completed'`).
		WithArgs(72).
		WillReturnResult(sqlmock.NewResult(0, 2))

	err := New(db, Options{OperationTimeout: time.Second}).UpdateRedactionReady(
		context.Background(),
		testMessage(),
	)

	require.NoError(t, err)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestLatestRetainsShorterCallerDeadline(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT compressionjobid, version, status, workload, createdat`).
		WithArgs(41).
		WillDelayFor(100 * time.Millisecond).
		WillReturnRows(jobRows().AddRow(41, 3, StatusCompleted, "normal", fixedCreatedAt))
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()

	_, _, err := New(db, Options{OperationTimeout: time.Second}).Latest(ctx, 41)

	assert.Error(t, err)
	assert.ErrorIs(t, err, context.DeadlineExceeded)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestLatestCapsOperationAtConfiguredTimeout(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectQuery(`SELECT compressionjobid, version, status, workload, createdat`).
		WithArgs(41).
		WillDelayFor(100 * time.Millisecond).
		WillReturnRows(jobRows().AddRow(41, 3, StatusCompleted, "normal", fixedCreatedAt))

	_, _, err := New(db, Options{OperationTimeout: 5 * time.Millisecond}).Latest(context.Background(), 41)

	assert.Error(t, err)
	assert.ErrorIs(t, err, context.DeadlineExceeded)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestEnsureStartedNormalizesOperationTimeout(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WillDelayFor(100 * time.Millisecond).
		WillReturnResult(sqlmock.NewResult(0, 1))

	_, err := New(db, Options{OperationTimeout: 5 * time.Millisecond}).EnsureStarted(
		context.Background(),
		testMessage(),
		config.WorkloadNormal,
	)

	assert.ErrorIs(t, err, context.DeadlineExceeded)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestFailNormalizesOperationTimeout(t *testing.T) {
	db, mock := newMock(t)
	mock.ExpectExec(`INSERT INTO public\."CompressionJob"`).
		WillDelayFor(100 * time.Millisecond).
		WillReturnResult(sqlmock.NewResult(0, 1))

	_, err := New(db, Options{OperationTimeout: 5 * time.Millisecond}).Fail(
		context.Background(),
		41,
		FailureCodeCompressionTimeout,
	)

	assert.ErrorIs(t, err, context.DeadlineExceeded)
	require.NoError(t, mock.ExpectationsWereMet())
}

func newMock(t *testing.T) (*sql.DB, sqlmock.Sqlmock) {
	t.Helper()
	db, mock, err := sqlmock.New(sqlmock.QueryMatcherOption(sqlmock.QueryMatcherRegexp))
	require.NoError(t, err)
	t.Cleanup(func() {
		if db.Stats().OpenConnections > 0 {
			mock.ExpectClose()
		}
		require.NoError(t, db.Close())
		require.NoError(t, mock.ExpectationsWereMet())
	})
	return db, mock
}

func jobRows() *sqlmock.Rows {
	return sqlmock.NewRows([]string{"compressionjobid", "version", "status", "workload", "createdat"})
}

func storedJobRows() *sqlmock.Rows {
	return sqlmock.NewRows([]string{
		"compressionjobid",
		"version",
		"status",
		"workload",
		"createdat",
		"documentmasterid",
		"ministryrequestid",
	})
}

func testMessage() models.CompressionProducerMessage {
	return models.CompressionProducerMessage{
		JobID:             41,
		MinistryRequestID: 72,
		Batch:             "batch-1",
		Trigger:           "recordupload",
		Filename:          "document.pdf",
		DocumentMasterID:  93,
	}
}

type retirementConnector struct {
	state *retirementDriverState
}

func (c retirementConnector) Connect(context.Context) (driver.Conn, error) {
	return c.state.open(), nil
}

func (c retirementConnector) Driver() driver.Driver {
	return retirementDriver{state: c.state}
}

type retirementDriver struct {
	state *retirementDriverState
}

func (d retirementDriver) Open(string) (driver.Conn, error) {
	return d.state.open(), nil
}

type retirementDriverState struct {
	mu     sync.Mutex
	opens  int
	closes int
}

func (s *retirementDriverState) open() driver.Conn {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.opens++
	return &retirementConn{id: s.opens, state: s}
}

func (s *retirementDriverState) openCount() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.opens
}

func (s *retirementDriverState) closeCount() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.closes
}

type retirementConn struct {
	id     int
	state  *retirementDriverState
	closed bool
}

func (c *retirementConn) Prepare(string) (driver.Stmt, error) {
	return nil, driver.ErrSkip
}

func (c *retirementConn) Close() error {
	c.state.mu.Lock()
	defer c.state.mu.Unlock()
	if !c.closed {
		c.state.closes++
		c.closed = true
	}
	return nil
}

func (c *retirementConn) Begin() (driver.Tx, error) {
	return nil, driver.ErrSkip
}

func (c *retirementConn) QueryContext(
	_ context.Context,
	query string,
	_ []driver.NamedValue,
) (driver.Rows, error) {
	switch {
	case strings.Contains(query, "pg_try_advisory_lock"):
		return &singleBoolRows{column: "locked", value: true}, nil
	case strings.Contains(query, "pg_advisory_unlock") && c.id == 1:
		return nil, errors.New("unlock failed")
	case strings.Contains(query, "pg_advisory_unlock"):
		return &singleBoolRows{column: "unlocked", value: true}, nil
	default:
		return nil, errors.New("unexpected query")
	}
}

type singleBoolRows struct {
	column string
	value  bool
	read   bool
}

func (r *singleBoolRows) Columns() []string {
	return []string{r.column}
}

func (r *singleBoolRows) Close() error {
	return nil
}

func (r *singleBoolRows) Next(values []driver.Value) error {
	if r.read {
		return io.EOF
	}
	r.read = true
	values[0] = r.value
	return nil
}
