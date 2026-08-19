package followup

import (
	"context"
	"io"
	"log/slog"
	"testing"

	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/go-redis/redis/v8"
)

func TestAfterTerminalPublishesOneFlatOCRMessageForPDF(t *testing.T) {
	t.Parallel()

	repository := &fakeRepository{ocrJobID: 77}
	publisher := &fakePublisher{}
	service := New(repository, publisher, "ocr", slog.New(slog.NewTextHandler(io.Discard, nil)))
	message := models.CompressionProducerMessage{JobID: 12, Filename: "record.pdf", Attributes: map[string]any{"filesize": 3}}

	service.AfterTerminal(context.Background(), message, store.CompressionResult{Status: store.StatusCompleted, Extension: ".pdf"})

	if repository.ensureCalls != 1 {
		t.Fatalf("EnsureOCRStarted calls = %d, want 1", repository.ensureCalls)
	}
	if repository.redactionCalls != 0 {
		t.Fatalf("UpdateRedactionReady calls = %d, want 0", repository.redactionCalls)
	}
	if publisher.calls != 1 || publisher.stream != "ocr" {
		t.Fatalf("publish = (%d, %q), want (1, ocr)", publisher.calls, publisher.stream)
	}
	if got := publisher.values["jobid"]; got != "77" {
		t.Fatalf("published jobid = %v, want 77", got)
	}
}

func TestAfterTerminalMarksNonPDFReadyForRedaction(t *testing.T) {
	t.Parallel()

	repository := &fakeRepository{}
	publisher := &fakePublisher{}
	service := New(repository, publisher, "ocr", slog.New(slog.NewTextHandler(io.Discard, nil)))
	message := models.CompressionProducerMessage{JobID: 12, Filename: "record.png"}

	service.AfterTerminal(context.Background(), message, store.CompressionResult{Status: store.StatusSkipped, Extension: ".png"})

	if repository.redactionCalls != 1 {
		t.Fatalf("UpdateRedactionReady calls = %d, want 1", repository.redactionCalls)
	}
	if repository.ensureCalls != 0 || publisher.calls != 0 {
		t.Fatalf("unexpected OCR publish work: ensure=%d publish=%d", repository.ensureCalls, publisher.calls)
	}
}

type fakeRepository struct {
	ocrJobID       int
	ensureCalls    int
	redactionCalls int
}

func (r *fakeRepository) EnsureOCRStarted(context.Context, models.CompressionProducerMessage) (int, error) {
	r.ensureCalls++
	return r.ocrJobID, nil
}

func (r *fakeRepository) UpdateRedactionReady(context.Context, models.CompressionProducerMessage) error {
	r.redactionCalls++
	return nil
}

type fakePublisher struct {
	calls  int
	stream string
	values map[string]any
}

func (p *fakePublisher) XAdd(_ context.Context, args *redis.XAddArgs) *redis.StringCmd {
	p.calls++
	p.stream = args.Stream
	p.values, _ = args.Values.(map[string]any)
	return redis.NewStringResult("1-0", nil)
}
