package consumer

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/config"
	"compressionservices/internal/contracts"
	"compressionservices/internal/store"
	"compressionservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
	messagingtest "github.com/bcgov/foi-messaging-go/testing"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type recordingProcessor struct {
	deliveries []compression.Delivery
	err        error
}

func (p *recordingProcessor) Process(_ context.Context, delivery compression.Delivery) error {
	p.deliveries = append(p.deliveries, delivery)
	return p.err
}

type typedNilProcessor struct{}

func (*typedNilProcessor) Process(context.Context, compression.Delivery) error {
	return nil
}

func TestStandard_DispatchesTypedDelivery(t *testing.T) {
	cfg := validStandardConfig()
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)
	payload := testCompressionMessage()
	event := newCompressionEvent(t, cfg.Messaging.Topic, payload)

	result, err := messagingtest.Dispatch(context.Background(), standard.consumer, event)

	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeProcessed, result.Outcome)
	require.Len(t, processor.deliveries, 1)
	assert.Equal(t, compression.Delivery{
		EventID:       "event-7",
		CorrelationID: "correlation-7",
		StreamID:      "",
		Workload:      config.WorkloadNormal,
		Message:       payload,
	}, processor.deliveries[0])
}

func TestStandard_RetryableFailureNacksWithSafeCauseChain(t *testing.T) {
	cause := errors.New("redis password=do-not-expose")
	failure := compression.NewRetryableFailure(store.FailureCodeDatabaseUnavailable, cause)
	processor := &recordingProcessor{err: failure}
	cfg := validStandardConfig()
	standard := newStandardForTest(t, cfg, processor)

	result, err := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, cfg.Messaging.Topic, testCompressionMessage()),
	)

	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeNacked, result.Outcome)
	assert.Equal(t, "retryable", result.Category)
	assert.Len(t, processor.deliveries, 4)
	require.Error(t, result.Err)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), result.Err.Error())
	assert.NotContains(t, result.Err.Error(), cause.Error())
	assert.True(t, messaging.IsRetryable(result.Err))
	assert.ErrorIs(t, result.Err, cause)
	var gotFailure *compression.Failure
	require.ErrorAs(t, result.Err, &gotFailure)
	assert.Same(t, failure, gotFailure)
}

func TestStandard_DeliveryAttemptSixDeadLettersBeforeProcessing(t *testing.T) {
	cfg := validStandardConfig()
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)

	result, err := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, cfg.Messaging.Topic, testCompressionMessage()),
		messagingtest.WithDeliveryAttempt(6),
	)

	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeDeadLettered, result.Outcome)
	assert.Equal(t, "max_attempts", result.Category)
	assert.Empty(t, processor.deliveries)
	require.Len(t, result.DeadLetters, 1)
	assert.Equal(t, messaging.ReasonMaxAttemptsExceeded, result.DeadLetters[0].Reason)
	assert.Equal(t, int64(6), result.DeadLetters[0].DeliveryAttempts)
	assert.Equal(t, cfg.Messaging.Topic, result.DeadLetters[0].OriginalTopic)
	assert.Equal(
		t,
		"delivery attempt 6 exceeded MaxDeliveryAttempts 5",
		result.DeadLetters[0].Error,
	)
}

func TestStandard_OtherWorkloadTopicSkips(t *testing.T) {
	cfg := validStandardConfig()
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)

	result, err := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, "compression-large", testCompressionMessage()),
	)

	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeSkipped, result.Outcome)
	assert.Equal(t, "no_handler", result.Reason)
	assert.Empty(t, processor.deliveries)
}

func TestStandard_LargeWorkloadDispatchesOnlyLargeTopic(t *testing.T) {
	cfg := validStandardConfig()
	cfg.Workload = config.WorkloadLarge
	cfg.ProcessingTimeout = 60 * time.Minute
	cfg.Messaging.Topic = "compression-large"
	cfg.Messaging.ConsumerGroup = "stable-large-workers"
	cfg.Messaging.ClaimMinIdle = 62 * time.Minute
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)
	payload := testCompressionMessage()

	largeResult, err := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, "compression-large", payload),
	)
	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeProcessed, largeResult.Outcome)
	require.Len(t, processor.deliveries, 1)
	assert.Equal(t, config.WorkloadLarge, processor.deliveries[0].Workload)
	assert.Equal(t, payload, processor.deliveries[0].Message)

	normalResult, err := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, "compression", payload),
	)
	require.NoError(t, err)
	assert.Equal(t, messagingtest.OutcomeSkipped, normalResult.Outcome)
	assert.Equal(t, "no_handler", normalResult.Reason)
	assert.Len(t, processor.deliveries, 1)
}

func TestStandard_RegistersConfiguredContractBeforeRun(t *testing.T) {
	cfg := validStandardConfig()
	standard := newStandardForTest(t, cfg, &recordingProcessor{})

	err := messaging.RegisterHandler(
		standard.consumer,
		contracts.CompressionRequested(cfg.Messaging.Topic),
		typedHandler{
			workload:  cfg.Workload,
			processor: &recordingProcessor{},
		},
	)

	require.Error(t, err)
	assert.Contains(t, err.Error(), "already registered")
}

func TestStandardMessagingConfig_MapsProductionSettings(t *testing.T) {
	cfg := validStandardConfig()
	logger := testLogger()

	got := standardMessagingConfig(cfg, logger)

	assert.Equal(t, "foi-docreviewer.compression", got.Source)
	assert.Equal(t, cfg.Messaging.StreamPrefix, got.StreamPrefix)
	assert.Equal(t, messaging.RedisConfig{
		Address:  cfg.Messaging.RedisAddress,
		Password: cfg.Messaging.RedisPassword,
	}, got.Redis)
	assert.Equal(t, messaging.ConsumerConfig{
		Group:               cfg.Messaging.ConsumerGroup,
		Concurrency:         1,
		ClaimInterval:       cfg.Messaging.ClaimInterval,
		ClaimMinIdle:        cfg.Messaging.ClaimMinIdle,
		MaxDeliveryAttempts: cfg.Messaging.MaxDeliveryAttempts,
		ShutdownTimeout:     cfg.Messaging.ShutdownTimeout,
	}, got.Consumer)
	assert.Same(t, logger, got.Telemetry.Logger)
	assert.False(t, got.Telemetry.LogPayloads)
}

func TestNewStandard_RejectsInvalidDependenciesAndConfiguration(t *testing.T) {
	tests := []struct {
		name      string
		configure func(*config.Config)
		logger    *slog.Logger
		processor DeliveryProcessor
	}{
		{
			name:      "nil logger",
			logger:    nil,
			processor: &recordingProcessor{},
		},
		{
			name:      "nil processor",
			logger:    testLogger(),
			processor: nil,
		},
		{
			name:      "typed nil processor",
			logger:    testLogger(),
			processor: (*typedNilProcessor)(nil),
		},
		{
			name: "non-standard mode",
			configure: func(cfg *config.Config) {
				cfg.Mode = config.ModeLegacy
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "unknown workload",
			configure: func(cfg *config.Config) {
				cfg.Workload = config.Workload("unknown")
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "zero processing timeout",
			configure: func(cfg *config.Config) {
				cfg.ProcessingTimeout = 0
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "negative processing timeout",
			configure: func(cfg *config.Config) {
				cfg.ProcessingTimeout = -time.Second
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "missing redis address",
			configure: func(cfg *config.Config) {
				cfg.Messaging.RedisAddress = ""
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "missing stream prefix",
			configure: func(cfg *config.Config) {
				cfg.Messaging.StreamPrefix = ""
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "non-approved stream prefix",
			configure: func(cfg *config.Config) {
				cfg.Messaging.StreamPrefix = "other"
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "missing topic",
			configure: func(cfg *config.Config) {
				cfg.Messaging.Topic = ""
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "normal workload on large topic",
			configure: func(cfg *config.Config) {
				cfg.Messaging.Topic = "compression-large"
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "large workload on normal topic",
			configure: func(cfg *config.Config) {
				cfg.Workload = config.WorkloadLarge
				cfg.ProcessingTimeout = 60 * time.Minute
				cfg.Messaging.ClaimMinIdle = 62 * time.Minute
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "missing consumer group",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ConsumerGroup = ""
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "zero claim interval",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ClaimInterval = 0
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "zero claim minimum idle",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ClaimMinIdle = 0
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "claim minimum idle below processing timeout",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ClaimMinIdle = 14 * time.Minute
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "claim minimum idle equals processing timeout",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ClaimMinIdle = cfg.ProcessingTimeout
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "zero delivery cap",
			configure: func(cfg *config.Config) {
				cfg.Messaging.MaxDeliveryAttempts = 0
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
		{
			name: "zero shutdown timeout",
			configure: func(cfg *config.Config) {
				cfg.Messaging.ShutdownTimeout = 0
			},
			logger:    testLogger(),
			processor: &recordingProcessor{},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			cfg := validStandardConfig()
			if tt.configure != nil {
				tt.configure(&cfg)
			}

			got, err := NewStandard(cfg, tt.logger, tt.processor)

			require.Error(t, err)
			assert.Nil(t, got)
			assert.NotContains(t, err.Error(), cfg.Messaging.RedisPassword)
			assert.NotContains(t, err.Error(), cfg.Database.Password)
		})
	}
}

func TestStandard_RunRejectsNilContextWithoutStartingConsumer(t *testing.T) {
	cfg := validStandardConfig()
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)

	err := standard.Run(nil)

	require.Error(t, err)
	assert.Contains(t, err.Error(), "context")
	result, dispatchErr := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, cfg.Messaging.Topic, testCompressionMessage()),
	)
	require.NoError(t, dispatchErr)
	assert.Equal(t, messagingtest.OutcomeProcessed, result.Outcome)
}

func TestStandard_RunRejectsCanceledContextWithoutStartingConsumer(t *testing.T) {
	cfg := validStandardConfig()
	processor := &recordingProcessor{}
	standard := newStandardForTest(t, cfg, processor)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	err := standard.Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	require.NoError(t, messaging.RegisterHandler(
		standard.consumer,
		messaging.EventDef{
			Topic:   cfg.Messaging.Topic,
			Type:    "document.compression.reviewed",
			Version: "1.0.0",
		},
		typedHandler{
			workload:  cfg.Workload,
			processor: processor,
		},
	))
	result, dispatchErr := messagingtest.Dispatch(
		context.Background(),
		standard.consumer,
		newCompressionEvent(t, cfg.Messaging.Topic, testCompressionMessage()),
	)
	require.NoError(t, dispatchErr)
	assert.Equal(t, messagingtest.OutcomeProcessed, result.Outcome)
}

func TestStandard_CloseDelegatesIdempotently(t *testing.T) {
	standard, err := NewStandard(validStandardConfig(), testLogger(), &recordingProcessor{})
	require.NoError(t, err)

	assert.NoError(t, standard.Close())
	assert.NoError(t, standard.Close())
}

func newStandardForTest(
	t *testing.T,
	cfg config.Config,
	processor DeliveryProcessor,
) *Standard {
	t.Helper()

	standard, err := NewStandard(cfg, testLogger(), processor)
	require.NoError(t, err)
	t.Cleanup(func() {
		require.NoError(t, standard.Close())
	})
	return standard
}

func newCompressionEvent(
	t *testing.T,
	topic string,
	payload models.CompressionProducerMessage,
) messagingtest.Event {
	t.Helper()

	event, err := messagingtest.NewEvent(
		contracts.CompressionRequested(topic),
		payload,
		messagingtest.WithEventID("event-7"),
		messagingtest.WithCorrelationID("correlation-7"),
	)
	require.NoError(t, err)
	return event
}

func validStandardConfig() config.Config {
	return config.Config{
		Mode:              config.ModeStandard,
		Workload:          config.WorkloadNormal,
		ProcessingTimeout: 15 * time.Minute,
		Messaging: config.Messaging{
			RedisAddress:        "redis.internal:6380",
			RedisPassword:       "redis-secret",
			StreamPrefix:        "foi",
			Topic:               "compression",
			ConsumerGroup:       "foi-compression",
			ClaimInterval:       30 * time.Second,
			ClaimMinIdle:        17 * time.Minute,
			MaxDeliveryAttempts: 5,
			ShutdownTimeout:     25 * time.Second,
		},
		Database: config.Database{Password: "database-secret"},
	}
}

func testCompressionMessage() models.CompressionProducerMessage {
	userToken := "token"
	outputDocumentMasterID := 202
	documentID := 303

	return models.CompressionProducerMessage{
		BCGovCode:              "abc",
		S3FilePath:             "source/document.pdf",
		RequestNumber:          "REQ-1",
		Filename:               "document.pdf",
		MinistryRequestID:      101,
		Batch:                  "batch-1",
		JobID:                  404,
		DocumentMasterID:       505,
		Trigger:                "upload",
		CreatedBy:              "tester",
		Incompatible:           false,
		UserToken:              &userToken,
		Attributes:             map[string]any{"extension": ".pdf", "pages": float64(2)},
		OutputDocumentMasterID: &outputDocumentMasterID,
		DocumentID:             &documentID,
	}
}

func testLogger() *slog.Logger {
	return slog.New(slog.NewTextHandler(io.Discard, nil))
}
