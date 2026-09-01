package consumer

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"ocrservices/internal/contracts"
	"ocrservices/internal/ocr"
	"ocrservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
	messagingtest "github.com/bcgov/foi-messaging-go/testing"
	"github.com/stretchr/testify/require"
)

type stubProcessor struct{ err error }

func (s stubProcessor) Process(_ context.Context, _ ocr.Delivery) error { return s.err }

func registeredHandler(t *testing.T, p ocr.DeliveryProcessor) messaging.Handler[models.OCRProducerMessage] {
	t.Helper()
	return handlerFor(slog.New(slog.NewTextHandler(io.Discard, nil)), p)
}

func newEnvelope(eventID, correlationID string, msg models.OCRProducerMessage) messaging.Envelope[models.OCRProducerMessage] {
	def := contracts.OCRRequested()
	return messaging.Envelope[models.OCRProducerMessage]{
		EventID:       eventID,
		EventType:     def.Type,
		Timestamp:     time.Now(),
		SchemaVersion: def.Version,
		CorrelationID: correlationID,
		Source:        "test",
		Payload:       msg,
	}
}

func TestHandlerRetryableOnTransientError(t *testing.T) {
	env := newEnvelope("e1", "", models.OCRProducerMessage{JobID: 1})
	handlerErr := messagingtest.Deliver(context.Background(),
		registeredHandler(t, stubProcessor{err: ocr.Retryable(errors.New("db down"))}), env)
	require.True(t, messaging.IsRetryable(handlerErr))
}

func TestHandlerPermanentOnPermanentError(t *testing.T) {
	env := newEnvelope("e2", "", models.OCRProducerMessage{JobID: 1})
	handlerErr := messagingtest.Deliver(context.Background(),
		registeredHandler(t, stubProcessor{err: ocr.Permanent(errors.New("bad payload"))}), env)
	require.True(t, messaging.IsPermanent(handlerErr))
}

func TestHandlerSuccessProcessed(t *testing.T) {
	env := newEnvelope("e3", "", models.OCRProducerMessage{JobID: 1})
	handlerErr := messagingtest.Deliver(context.Background(),
		registeredHandler(t, stubProcessor{}), env)
	require.NoError(t, handlerErr)
}

func TestHandlerPropagatesEventAndCorrelationIDs(t *testing.T) {
	var captured ocr.Delivery
	proc := captureProcessor{fn: func(d ocr.Delivery) { captured = d }}

	env := newEnvelope("evt-42", "corr-99", models.OCRProducerMessage{JobID: 2})
	handlerErr := messagingtest.Deliver(context.Background(), registeredHandler(t, proc), env)
	require.NoError(t, handlerErr)
	require.Equal(t, "evt-42", captured.EventID)
	require.Equal(t, "corr-99", captured.CorrelationID)
}

type captureProcessor struct{ fn func(ocr.Delivery) }

func (c captureProcessor) Process(_ context.Context, d ocr.Delivery) error {
	c.fn(d)
	return nil
}
