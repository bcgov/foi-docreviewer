// Package followup performs best-effort work after a compression job is terminal.
package followup

import (
	"context"
	"log/slog"
	"strings"

	"compressionservices/internal/contracts"
	"compressionservices/internal/store"
	"compressionservices/models"

	messaging "github.com/bcgov/foi-messaging-go"
)

// Repository owns the durable state changes required before follow-up work.
type Repository interface {
	EnsureOCRStarted(context.Context, models.CompressionProducerMessage) (int, error)
	UpdateRedactionReady(context.Context, models.CompressionProducerMessage) error
}

// Publisher is the narrow subset of *messaging.Publisher used to publish OCR work.
type Publisher interface {
	Publish(context.Context, messaging.EventDef, any, ...messaging.PublishOption) (messaging.PublishResult, error)
}

// Service preserves the existing best-effort OCR/redaction follow-up behavior.
type Service struct {
	repository Repository
	publisher  Publisher
	logger     *slog.Logger
}

// New creates a follow-up service using the shared messaging publisher.
func New(repository Repository, publisher Publisher, logger *slog.Logger) *Service {
	return &Service{repository: repository, publisher: publisher, logger: logger}
}

// AfterTerminal sends PDFs to OCR and marks other successful documents ready
// for redaction. Failures are logged as safe codes and never change the
// confirmed compression outcome.
func (s *Service) AfterTerminal(
	ctx context.Context,
	message models.CompressionProducerMessage,
	result store.CompressionResult,
) {
	if s == nil || s.repository == nil || s.logger == nil || ctx == nil {
		return
	}
	if result.Status != store.StatusCompleted && result.Status != store.StatusSkipped {
		return
	}
	if strings.EqualFold(result.Extension, ".pdf") {
		s.publishOCR(ctx, message)
		return
	}
	if err := s.repository.UpdateRedactionReady(ctx, message); err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "redaction_update_failed", "job_id", message.JobID)
	}
}

func (s *Service) publishOCR(ctx context.Context, message models.CompressionProducerMessage) {
	if s.publisher == nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_publish_unavailable", "job_id", message.JobID)
		return
	}
	jobID, err := s.repository.EnsureOCRStarted(ctx, message)
	if err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_start_failed", "job_id", message.JobID)
		return
	}
	// Correlation ID propagates from ctx automatically (library resolves it).
	if _, err := s.publisher.Publish(ctx, contracts.OCRRequested(), toOCRPayload(message, jobID)); err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_publish_failed", "job_id", jobID)
	}
}

func toOCRPayload(m models.CompressionProducerMessage, ocrJobID int) contracts.OCREventPayload {
	documentID := 0
	if m.DocumentID != nil {
		documentID = *m.DocumentID
	}
	incompatible := m.Incompatible
	return contracts.OCREventPayload{
		BCGovCode:            m.BCGovCode,
		S3FilePath:           m.S3FilePath,
		RequestNumber:        m.RequestNumber,
		Filename:             m.Filename,
		MinistryRequestID:    m.MinistryRequestID,
		Batch:                m.Batch,
		JobID:                ocrJobID,
		DocumentMasterID:     m.DocumentMasterID,
		Trigger:              m.Trigger,
		CreatedBy:            m.CreatedBy,
		CompressedS3FilePath: m.CompressedS3FilePath,
		DocumentID:           documentID,
		Incompatible:         &incompatible,
		UserToken:            m.UserToken,
	}
}
