// Package consumer adapts compression processing to its supported transports.
package consumer

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"reflect"
	"strings"

	"compressionservices/internal/compression"
	"compressionservices/internal/config"
	"compressionservices/internal/contracts"
	"compressionservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
)

const (
	standardSource       = "foi-docreviewer.compression"
	standardStreamPrefix = "foi"
	standardNormalTopic  = "compression"
	standardLargeTopic   = "compression-large"
)

var (
	errStandardLoggerRequired    = errors.New("standard consumer logger is required")
	errStandardProcessorRequired = errors.New("standard consumer processor is required")
	errStandardContextRequired   = errors.New("standard consumer context is required")
	errStandardUnavailable       = errors.New("standard consumer is unavailable")
)

// DeliveryProcessor processes one transport-independent compression delivery.
type DeliveryProcessor interface {
	Process(context.Context, compression.Delivery) error
}

// Standard consumes the typed standard compression event.
type Standard struct {
	consumer *messaging.Consumer
}

// NewStandard builds a standard consumer and registers its sole typed handler.
// A logger is required so the messaging library uses the application-owned
// logger rather than silently falling back to slog.Default.
func NewStandard(
	cfg config.Config,
	logger *slog.Logger,
	processor DeliveryProcessor,
) (*Standard, error) {
	if logger == nil {
		return nil, errStandardLoggerRequired
	}
	if isNilDeliveryProcessor(processor) {
		return nil, errStandardProcessorRequired
	}
	if err := validateStandardConfig(cfg); err != nil {
		return nil, fmt.Errorf("invalid standard consumer config: %w", err)
	}

	consumer, err := messaging.NewConsumer(standardMessagingConfig(cfg, logger))
	if err != nil {
		return nil, fmt.Errorf("creating standard messaging consumer: %w", err)
	}

	handler := typedHandler{
		workload:  cfg.Workload,
		processor: processor,
	}
	if err := messaging.RegisterHandler(
		consumer,
		contracts.CompressionRequested(cfg.Messaging.Topic),
		handler,
	); err != nil {
		return nil, fmt.Errorf("registering compression event handler: %w", err)
	}

	return &Standard{consumer: consumer}, nil
}

// Run delegates the blocking consumer lifecycle to foi-messaging-go.
func (s *Standard) Run(ctx context.Context) error {
	if ctx == nil {
		return errStandardContextRequired
	}
	if s == nil || s.consumer == nil {
		return errStandardUnavailable
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	return s.consumer.Run(ctx)
}

// Close delegates resource release to foi-messaging-go.
func (s *Standard) Close() error {
	if s == nil || s.consumer == nil {
		return errStandardUnavailable
	}
	return s.consumer.Close()
}

type typedHandler struct {
	workload  config.Workload
	processor DeliveryProcessor
}

func (h typedHandler) Handle(
	ctx context.Context,
	envelope messaging.Envelope[models.CompressionProducerMessage],
) error {
	err := h.processor.Process(ctx, compression.Delivery{
		EventID:       envelope.EventID,
		CorrelationID: envelope.CorrelationID,
		Workload:      h.workload,
		Message:       envelope.Payload,
	})
	if err != nil {
		return messaging.AsRetryable(err)
	}
	return nil
}

func standardMessagingConfig(cfg config.Config, logger *slog.Logger) messaging.Config {
	return messaging.Config{
		Source:       standardSource,
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
		Telemetry: messaging.TelemetryConfig{
			Logger:      logger,
			LogPayloads: false,
		},
	}
}

func validateStandardConfig(cfg config.Config) error {
	if cfg.Mode != config.ModeStandard {
		return errors.New("mode must be standard")
	}
	if cfg.Workload != config.WorkloadNormal && cfg.Workload != config.WorkloadLarge {
		return errors.New("workload must be normal or large")
	}
	if cfg.ProcessingTimeout <= 0 {
		return errors.New("processing timeout must be positive")
	}
	if strings.TrimSpace(cfg.Messaging.RedisAddress) == "" {
		return errors.New("redis address is required")
	}
	if strings.TrimSpace(cfg.Messaging.StreamPrefix) == "" {
		return errors.New("stream prefix is required")
	}
	if cfg.Messaging.StreamPrefix != standardStreamPrefix {
		return errors.New("stream prefix must be foi")
	}
	if strings.TrimSpace(cfg.Messaging.Topic) == "" {
		return errors.New("topic is required")
	}
	if cfg.Workload == config.WorkloadNormal && cfg.Messaging.Topic != standardNormalTopic {
		return errors.New("normal workload topic must be compression")
	}
	if cfg.Workload == config.WorkloadLarge && cfg.Messaging.Topic != standardLargeTopic {
		return errors.New("large workload topic must be compression-large")
	}
	if strings.TrimSpace(cfg.Messaging.ConsumerGroup) == "" {
		return errors.New("consumer group is required")
	}
	if cfg.Messaging.ClaimInterval <= 0 {
		return errors.New("claim interval must be positive")
	}
	if cfg.Messaging.ClaimMinIdle <= 0 {
		return errors.New("claim minimum idle must be positive")
	}
	if cfg.Messaging.ClaimMinIdle < cfg.Messaging.ClaimInterval {
		return errors.New("claim minimum idle must not be shorter than claim interval")
	}
	if cfg.Messaging.ClaimMinIdle <= cfg.ProcessingTimeout {
		return errors.New("claim minimum idle must exceed processing timeout")
	}
	if cfg.Messaging.MaxDeliveryAttempts <= 0 {
		return errors.New("maximum delivery attempts must be positive")
	}
	if cfg.Messaging.ShutdownTimeout <= 0 {
		return errors.New("shutdown timeout must be positive")
	}
	return nil
}

func isNilDeliveryProcessor(processor DeliveryProcessor) bool {
	if processor == nil {
		return true
	}

	value := reflect.ValueOf(processor)
	switch value.Kind() {
	case reflect.Chan, reflect.Func, reflect.Interface, reflect.Map, reflect.Pointer, reflect.Slice:
		return value.IsNil()
	default:
		return false
	}
}
