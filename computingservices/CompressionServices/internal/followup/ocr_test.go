package followup

import (
	"context"
	"io"
	"log/slog"
	"testing"

	"compressionservices/internal/contracts"
	"compressionservices/internal/store"
	"compressionservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
)

func TestAfterTerminalPublishesOneFlatOCRMessageForPDF(t *testing.T) {
	t.Parallel()

	repository := &fakeRepository{ocrJobID: 77}
	publisher := &fakePublisher{}
	service := New(repository, publisher, slog.New(slog.NewTextHandler(io.Discard, nil)))
	message := models.CompressionProducerMessage{JobID: 12, Filename: "record.pdf", Attributes: map[string]any{"filesize": 3}}

	service.AfterTerminal(context.Background(), message, store.CompressionResult{Status: store.StatusCompleted, Extension: ".pdf"})

	if repository.ensureCalls != 1 {
		t.Fatalf("EnsureOCRStarted calls = %d, want 1", repository.ensureCalls)
	}
	if repository.redactionCalls != 0 {
		t.Fatalf("UpdateRedactionReady calls = %d, want 0", repository.redactionCalls)
	}
	if publisher.calls != 1 {
		t.Fatalf("publish calls = %d, want 1", publisher.calls)
	}
	if publisher.lastDef.Type != "document.ocr.requested" {
		t.Fatalf("type = %q", publisher.lastDef.Type)
	}
	if publisher.lastPayload.JobID != 77 {
		t.Fatalf("published jobid = %d, want 77", publisher.lastPayload.JobID)
	}
}

func TestAfterTerminalForwardsIncompatibleAndUserToken(t *testing.T) {
	t.Parallel()

	token := "tok-abc"
	repository := &fakeRepository{ocrJobID: 5}
	publisher := &fakePublisher{}
	service := New(repository, publisher, slog.New(slog.NewTextHandler(io.Discard, nil)))
	message := models.CompressionProducerMessage{
		JobID:        12,
		Filename:     "record.pdf",
		Incompatible: true,
		UserToken:    &token,
		Attributes:   map[string]any{},
	}

	service.AfterTerminal(context.Background(), message, store.CompressionResult{Status: store.StatusCompleted, Extension: ".pdf"})

	if publisher.calls != 1 {
		t.Fatalf("publish calls = %d, want 1", publisher.calls)
	}
	if publisher.lastPayload.Incompatible == nil || !*publisher.lastPayload.Incompatible {
		t.Fatalf("Incompatible = %v, want pointer to true", publisher.lastPayload.Incompatible)
	}
	if publisher.lastPayload.UserToken == nil || *publisher.lastPayload.UserToken != "tok-abc" {
		t.Fatalf("UserToken = %v, want pointer to %q", publisher.lastPayload.UserToken, "tok-abc")
	}
}

func TestAfterTerminalMarksNonPDFReadyForRedaction(t *testing.T) {
	t.Parallel()

	repository := &fakeRepository{}
	publisher := &fakePublisher{}
	service := New(repository, publisher, slog.New(slog.NewTextHandler(io.Discard, nil)))
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
	calls       int
	lastDef     messaging.EventDef
	lastPayload contracts.OCREventPayload
	err         error
}

func (f *fakePublisher) Publish(_ context.Context, def messaging.EventDef, payload any,
	_ ...messaging.PublishOption) (messaging.PublishResult, error) {
	f.calls++
	f.lastDef = def
	if p, ok := payload.(contracts.OCREventPayload); ok {
		f.lastPayload = p
	}
	return messaging.PublishResult{EventID: "evt-1"}, f.err
}
