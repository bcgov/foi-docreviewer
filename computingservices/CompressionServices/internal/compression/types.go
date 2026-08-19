// Package compression coordinates idempotent compression job processing.
package compression

import (
	"context"
	"time"

	"compressionservices/internal/config"
	"compressionservices/internal/store"
	"compressionservices/models"
)

type Delivery struct {
	EventID       string
	CorrelationID string
	StreamID      string
	Workload      config.Workload
	Message       models.CompressionProducerMessage
}

type Repository interface {
	WithinJobLock(context.Context, int, func(context.Context) error) (bool, error)
	Latest(context.Context, int) (store.Job, bool, error)
	EnsureStarted(
		context.Context,
		models.CompressionProducerMessage,
		config.Workload,
	) (store.Job, error)
	Complete(
		context.Context,
		models.CompressionProducerMessage,
		store.CompressionResult,
	) (store.Job, error)
	Fail(context.Context, int, store.FailureCode) (store.Job, error)
}

var _ Repository = (*store.Repository)(nil)

type Processor interface {
	Compress(context.Context, models.CompressionProducerMessage) (store.CompressionResult, error)
}

type FollowUp interface {
	AfterTerminal(context.Context, models.CompressionProducerMessage, store.CompressionResult)
}

type Options struct {
	Workload            config.Workload
	ProcessingTimeout   time.Duration
	FinalizationTimeout time.Duration
	Now                 func() time.Time
}
