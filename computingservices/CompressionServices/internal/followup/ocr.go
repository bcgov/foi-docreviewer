// Package followup performs best-effort work after a compression job is terminal.
package followup

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"

	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/go-redis/redis/v8"
)

// Repository owns the durable state changes required before follow-up work.
type Repository interface {
	EnsureOCRStarted(context.Context, models.CompressionProducerMessage) (int, error)
	UpdateRedactionReady(context.Context, models.CompressionProducerMessage) error
}

// Publisher is the subset of the shared Redis client used to publish OCR work.
type Publisher interface {
	XAdd(context.Context, *redis.XAddArgs) *redis.StringCmd
}

// Service preserves the existing best-effort OCR/redaction follow-up behavior.
type Service struct {
	repository Repository
	publisher  Publisher
	stream     string
	logger     *slog.Logger
}

// New creates a follow-up service using the process-owned Redis client.
func New(repository Repository, publisher Publisher, stream string, logger *slog.Logger) *Service {
	return &Service{
		repository: repository,
		publisher:  publisher,
		stream:     strings.TrimSpace(stream),
		logger:     logger,
	}
}

// AfterTerminal sends PDFs to OCR and marks other successful documents ready
// for redaction. Failures are intentionally logged as safe codes and do not
// change the confirmed compression outcome.
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
	if s.publisher == nil || s.stream == "" {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_publish_unavailable", "job_id", message.JobID)
		return
	}

	jobID, err := s.repository.EnsureOCRStarted(ctx, message)
	if err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_start_failed", "job_id", message.JobID)
		return
	}
	message.JobID = jobID
	values, err := flatMessage(message)
	if err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_payload_invalid", "job_id", message.JobID)
		return
	}
	if err := s.publisher.XAdd(ctx, &redis.XAddArgs{Stream: s.stream, Values: values}).Err(); err != nil {
		s.logger.Warn("compression_follow_up_failed", "error_code", "ocr_publish_failed", "job_id", message.JobID)
	}
}

func flatMessage(message models.CompressionProducerMessage) (map[string]any, error) {
	encoded, err := json.Marshal(message)
	if err != nil {
		return nil, err
	}
	var decoded map[string]any
	if err := json.Unmarshal(encoded, &decoded); err != nil {
		return nil, err
	}
	flat := make(map[string]any, len(decoded))
	for key, value := range decoded {
		flat[key] = fmt.Sprint(value)
	}
	return flat, nil
}
