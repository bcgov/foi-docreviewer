package consumer

import (
	"context"
	"errors"
	"fmt"
	"log/slog"

	"ocrservices/internal/config"
	"ocrservices/internal/contracts"
	"ocrservices/internal/ocr"
	"ocrservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
)

const source = "foi-docreviewer.ocr"

// ocrHandlerAdapter adapts a closure to the messaging.Handler[T] interface.
type ocrHandlerAdapter struct {
	fn func(context.Context, messaging.Envelope[models.OCRProducerMessage]) error
}

func (h ocrHandlerAdapter) Handle(ctx context.Context, env messaging.Envelope[models.OCRProducerMessage]) error {
	return h.fn(ctx, env)
}

// Standard consumes the typed OCR event via foi-messaging-go.
type Standard struct{ consumer *messaging.Consumer }

// NewStandard builds a consumer and registers the typed OCR handler.
func NewStandard(cfg config.Config, logger *slog.Logger, processor ocr.DeliveryProcessor) (*Standard, error) {
	if logger == nil {
		return nil, errors.New("logger is required")
	}
	if processor == nil {
		return nil, errors.New("processor is required")
	}
	c, err := messaging.NewConsumer(messagingConfig(cfg, logger))
	if err != nil {
		return nil, fmt.Errorf("creating ocr consumer: %w", err)
	}
	if err := messaging.RegisterHandler(c, contracts.OCRRequested(), handlerFor(logger, processor)); err != nil {
		return nil, fmt.Errorf("registering ocr handler: %w", err)
	}
	return &Standard{consumer: c}, nil
}

// Run blocks until ctx is cancelled, then drains in-flight handlers.
func (s *Standard) Run(ctx context.Context) error { return s.consumer.Run(ctx) }

// Close releases consumer resources.
func (s *Standard) Close() error { return s.consumer.Close() }

// handlerFor returns the typed Handler registered for the OCR event.
func handlerFor(logger *slog.Logger, processor ocr.DeliveryProcessor) messaging.Handler[models.OCRProducerMessage] {
	return ocrHandlerAdapter{fn: func(ctx context.Context, env messaging.Envelope[models.OCRProducerMessage]) error {
		logger.Debug("ocr_event_received", "event_id", env.EventID, "job_id", env.Payload.JobID)
		err := processor.Process(ctx, ocr.Delivery{
			EventID:       env.EventID,
			CorrelationID: env.CorrelationID,
			Message:       env.Payload,
		})
		if err == nil {
			return nil
		}
		if ocr.IsPermanent(err) {
			return messaging.AsPermanent(err)
		}
		return messaging.AsRetryable(err)
	}}
}

func messagingConfig(cfg config.Config, logger *slog.Logger) messaging.Config {
	return messaging.Config{
		Source:       source,
		StreamPrefix: cfg.Messaging.StreamPrefix,
		Redis: messaging.RedisConfig{
			Address:  cfg.Messaging.RedisAddress,
			Password: cfg.Messaging.RedisPassword,
		},
		Consumer: messaging.ConsumerConfig{
			Group:               cfg.Messaging.ConsumerGroup,
			ConsumerName:        cfg.Messaging.ConsumerName,
			Concurrency:         1,
			ClaimInterval:       cfg.Messaging.ClaimInterval,
			ClaimMinIdle:        cfg.Messaging.ClaimMinIdle,
			MaxDeliveryAttempts: cfg.Messaging.MaxDeliveryAttempts,
			ShutdownTimeout:     cfg.Messaging.ShutdownTimeout,
		},
		Telemetry: messaging.TelemetryConfig{Logger: logger, LogPayloads: false},
	}
}
