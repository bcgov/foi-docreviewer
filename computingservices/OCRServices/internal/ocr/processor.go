package ocr

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"ocrservices/internal/activemq"
	"ocrservices/models"
)

var errInvalidJobID = errors.New("invalid ocr job id")

// Delivery is a transport-independent OCR work item.
type Delivery struct {
	EventID       string
	CorrelationID string
	Message       models.OCRProducerMessage
}

// DeliveryProcessor processes one OCR delivery.
type DeliveryProcessor interface {
	Process(context.Context, Delivery) error
}

// Repository is the durable OCR job state the processor depends on.
type Repository interface {
	TerminalExists(context.Context, int) (bool, error)
	EnsureStarted(context.Context, models.OCRProducerMessage) error
	RecordCompleted(context.Context, models.OCRProducerMessage) error
	RecordFailed(context.Context, models.OCRProducerMessage, string) error
}

// Pusher enqueues a document for OCR.
type Pusher interface {
	Push(context.Context, models.OCRAzureMessage) error
}

// Processor orchestrates an idempotent, classified OCR delivery.
type Processor struct {
	repo    Repository
	pusher  Pusher
	timeout time.Duration
	logger  *slog.Logger
}

// NewProcessor builds a Processor. If logger is nil, falls back to slog.Default().
func NewProcessor(repo Repository, pusher Pusher, timeout time.Duration, logger *slog.Logger) *Processor {
	if logger == nil {
		logger = slog.Default()
	}
	return &Processor{repo: repo, pusher: pusher, timeout: timeout, logger: logger}
}

// Process is idempotent on the OCR job id and classifies its failures.
func (p *Processor) Process(ctx context.Context, d Delivery) error {
	msg := d.Message
	if msg.JobID <= 0 {
		return Permanent(errInvalidJobID)
	}

	ctx, cancel := context.WithTimeout(ctx, p.timeout)
	defer cancel()

	p.logger.Info("message_received", "job_id", msg.JobID, "ministry_request_id", msg.MinistryRequestID, "document_master_id", msg.DocumentMasterID)

	terminal, err := p.repo.TerminalExists(ctx, msg.JobID)
	if err != nil {
		return Retryable(err)
	}
	if terminal {
		p.logger.Info("message_already_processed", "job_id", msg.JobID)
		return nil
	}

	if err := p.repo.EnsureStarted(ctx, msg); err != nil {
		return Retryable(err)
	}

	pushErr := p.pusher.Push(ctx, toAzureMessage(msg))
	if pushErr != nil {
		if activemq.IsPermanent(pushErr) {
			p.logger.Error("ocr_failed", "job_id", msg.JobID, "failure_code", "activemq_rejected")
			if recErr := p.repo.RecordFailed(ctx, msg, "activemq_rejected"); recErr != nil {
				return Retryable(recErr)
			}
			return Permanent(pushErr)
		}
		p.logger.Warn("ocr_failed", "job_id", msg.JobID, "failure_code", "activemq_unavailable")
		return Retryable(pushErr)
	}

	if err := p.repo.RecordCompleted(ctx, msg); err != nil {
		return Retryable(err)
	}
	p.logger.Info("message_completed", "job_id", msg.JobID)
	return nil
}

func toAzureMessage(m models.OCRProducerMessage) models.OCRAzureMessage {
	return models.OCRAzureMessage{
		BCGovCode:            m.BCGovCode,
		RequestNumber:        m.RequestNumber,
		MinistryRequestID:    m.MinistryRequestID,
		DocumentMasterID:     m.DocumentMasterID,
		Trigger:              m.Trigger,
		S3FilePath:           m.S3FilePath,
		CompressedS3FilePath: m.CompressedS3FilePath,
		DocumentID:           m.DocumentID,
	}
}
