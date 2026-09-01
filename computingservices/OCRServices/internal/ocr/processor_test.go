package ocr

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"ocrservices/internal/activemq"
	"ocrservices/models"

	"github.com/stretchr/testify/require"
)

type fakeRepo struct {
	terminal        bool
	terminalErr     error
	startedErr      error
	completedErr    error
	recordFailedErr error
	started         int
	completed       int
	failed          int
	lastFailCode    string
}

func (f *fakeRepo) TerminalExists(context.Context, int) (bool, error) {
	return f.terminal, f.terminalErr
}
func (f *fakeRepo) EnsureStarted(context.Context, models.OCRProducerMessage) error {
	f.started++
	return f.startedErr
}
func (f *fakeRepo) RecordCompleted(context.Context, models.OCRProducerMessage) error {
	f.completed++
	return f.completedErr
}
func (f *fakeRepo) RecordFailed(_ context.Context, _ models.OCRProducerMessage, code string) error {
	f.failed++
	f.lastFailCode = code
	return f.recordFailedErr
}

type fakePusher struct {
	err   error
	calls int
}

func (f *fakePusher) Push(context.Context, models.OCRAzureMessage) error {
	f.calls++
	return f.err
}

func newProc(repo Repository, pusher Pusher) *Processor {
	return NewProcessor(repo, pusher, time.Minute, slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func delivery() Delivery {
	return Delivery{
		EventID: "e1",
		Message: models.OCRProducerMessage{
			JobID:            5,
			DocumentMasterID: 9,
			MinistryRequestID: 42,
			BCGovCode:        "BCGOV",
			RequestNumber:    "FOI-001",
			Trigger:          "auto",
			S3FilePath:       "s3://bucket/file.pdf",
		},
	}
}

func TestProcessHappyPath(t *testing.T) {
	repo := &fakeRepo{}
	pusher := &fakePusher{}
	require.NoError(t, newProc(repo, pusher).Process(context.Background(), delivery()))
	require.Equal(t, 1, repo.started)
	require.Equal(t, 1, pusher.calls)
	require.Equal(t, 1, repo.completed)
	require.Equal(t, 0, repo.failed)
}

func TestProcessSkipsWhenTerminal(t *testing.T) {
	repo := &fakeRepo{terminal: true}
	pusher := &fakePusher{}
	require.NoError(t, newProc(repo, pusher).Process(context.Background(), delivery()))
	require.Equal(t, 0, pusher.calls)
	require.Equal(t, 0, repo.started)
	require.Equal(t, 0, repo.completed)
}

func TestProcessInvalidJobIDIsPermanent(t *testing.T) {
	err := newProc(&fakeRepo{}, &fakePusher{}).Process(
		context.Background(),
		Delivery{Message: models.OCRProducerMessage{JobID: 0}},
	)
	require.True(t, IsPermanent(err))
}

func TestProcessNegativeJobIDIsPermanent(t *testing.T) {
	err := newProc(&fakeRepo{}, &fakePusher{}).Process(
		context.Background(),
		Delivery{Message: models.OCRProducerMessage{JobID: -1}},
	)
	require.True(t, IsPermanent(err))
}

func TestProcessTerminalExistsErrorIsRetryable(t *testing.T) {
	err := newProc(
		&fakeRepo{terminalErr: errors.New("db down")},
		&fakePusher{},
	).Process(context.Background(), delivery())
	require.Error(t, err)
	require.False(t, IsPermanent(err))
}

func TestProcessEnsureStartedErrorIsRetryable(t *testing.T) {
	repo := &fakeRepo{startedErr: errors.New("db timeout")}
	err := newProc(repo, &fakePusher{}).Process(context.Background(), delivery())
	require.Error(t, err)
	require.False(t, IsPermanent(err))
	require.Equal(t, 0, repo.completed)
}

func TestProcessRecordCompletedErrorIsRetryable(t *testing.T) {
	repo := &fakeRepo{completedErr: errors.New("db timeout")}
	pusher := &fakePusher{}
	err := newProc(repo, pusher).Process(context.Background(), delivery())
	require.Error(t, err)
	require.False(t, IsPermanent(err))
	require.Equal(t, 1, pusher.calls)
}

func TestProcessPushPermanentRecordsFailedAndIsPermanent(t *testing.T) {
	repo := &fakeRepo{}
	pusher := &fakePusher{err: activemq.ErrPermanent}
	err := newProc(repo, pusher).Process(context.Background(), delivery())
	require.True(t, IsPermanent(err))
	require.Equal(t, 1, repo.failed)
	require.Equal(t, "activemq_rejected", repo.lastFailCode)
}

func TestProcessPushPermanentRecordFailedErrorIsRetryable(t *testing.T) {
	repo := &fakeRepo{recordFailedErr: errors.New("db down")}
	pusher := &fakePusher{err: activemq.ErrPermanent}
	err := newProc(repo, pusher).Process(context.Background(), delivery())
	require.Error(t, err)
	require.False(t, IsPermanent(err), "persistence failure must be retryable")
	require.Equal(t, 1, repo.failed, "RecordFailed must be attempted")
}

func TestProcessPushTransientIsRetryableAndDoesNotRecordTerminal(t *testing.T) {
	repo := &fakeRepo{}
	pusher := &fakePusher{err: errors.New("connection reset")}
	err := newProc(repo, pusher).Process(context.Background(), delivery())
	require.Error(t, err)
	require.False(t, IsPermanent(err))
	require.Equal(t, 0, repo.failed)
	require.Equal(t, 0, repo.completed)
}

func TestToAzureMessageMapsAllSupportedFields(t *testing.T) {
	src := models.OCRProducerMessage{
		BCGovCode:            "BCGOV",
		RequestNumber:        "FOI-001",
		MinistryRequestID:    42,
		DocumentMasterID:     99,
		Trigger:              "auto",
		S3FilePath:           "s3://bucket/in.pdf",
		CompressedS3FilePath: "s3://bucket/in.zip",
		DocumentID:           7,
		// Fields not in OCRAzureMessage — must not cause compile errors.
		JobID:    5,
		Filename: "file.pdf",
		Batch:    "batch1",
	}
	got := toAzureMessage(src)
	require.Equal(t, src.BCGovCode, got.BCGovCode)
	require.Equal(t, src.RequestNumber, got.RequestNumber)
	require.Equal(t, src.MinistryRequestID, got.MinistryRequestID)
	require.Equal(t, src.DocumentMasterID, got.DocumentMasterID)
	require.Equal(t, src.Trigger, got.Trigger)
	require.Equal(t, src.S3FilePath, got.S3FilePath)
	require.Equal(t, src.CompressedS3FilePath, got.CompressedS3FilePath)
	require.Equal(t, src.DocumentID, got.DocumentID)
}
