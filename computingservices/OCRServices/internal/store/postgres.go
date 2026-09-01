package store

import (
	"context"
	"database/sql"

	"ocrservices/models"
)

const (
	versionStarted  = 2
	versionTerminal = 3
	statusStarted   = "started"
	statusCompleted = "completed"
	statusError     = "error"
)

const (
	sqlTerminalExists = `SELECT COUNT(ocractivemqjobid) FROM public."OCRActiveMQJob" WHERE ocractivemqjobid = $1 AND version = $2`
	sqlEnsureStarted  = `INSERT INTO public."OCRActiveMQJob"` +
		` (ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)` +
		` VALUES ($1, $2, $3, $4, $5, $6, $7, $8)` +
		` ON CONFLICT (ocractivemqjobid, version) DO NOTHING`
	sqlRecordCompleted = `INSERT INTO public."OCRActiveMQJob"` +
		` (ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)` +
		` VALUES ($1, $2, $3, $4, $5, $6, $7, $8)` +
		` ON CONFLICT (ocractivemqjobid, version) DO NOTHING`
	sqlRecordFailed = `INSERT INTO public."OCRActiveMQJob"` +
		` (ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, message)` +
		` VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)` +
		` ON CONFLICT (ocractivemqjobid, version) DO NOTHING`
)

// Store is the OCR job repository over a shared pooled *sql.DB.
type Store struct{ db *sql.DB }

// New returns a Store backed by db.
func New(db *sql.DB) *Store { return &Store{db: db} }

// TerminalExists reports whether the job already has a terminal (version 3) row.
func (s *Store) TerminalExists(ctx context.Context, jobID int) (bool, error) {
	var count int
	err := s.db.QueryRowContext(ctx, sqlTerminalExists, jobID, versionTerminal).Scan(&count)
	if err != nil {
		return false, err
	}
	return count > 0, nil
}

// EnsureStarted idempotently records the started (version 2) row.
func (s *Store) EnsureStarted(ctx context.Context, m models.OCRProducerMessage) error {
	_, err := s.db.ExecContext(ctx, sqlEnsureStarted,
		m.JobID, versionStarted, m.MinistryRequestID, m.Batch, m.Trigger, m.Filename, statusStarted, m.DocumentMasterID)
	return err
}

// RecordCompleted idempotently records the terminal completed (version 3) row.
func (s *Store) RecordCompleted(ctx context.Context, m models.OCRProducerMessage) error {
	_, err := s.db.ExecContext(ctx, sqlRecordCompleted,
		m.JobID, versionTerminal, m.MinistryRequestID, m.Batch, m.Trigger, m.Filename, statusCompleted, m.DocumentMasterID)
	return err
}

// RecordFailed idempotently records the terminal error (version 3) row.
func (s *Store) RecordFailed(ctx context.Context, m models.OCRProducerMessage, message string) error {
	_, err := s.db.ExecContext(ctx, sqlRecordFailed,
		m.JobID, versionTerminal, m.MinistryRequestID, m.Batch, m.Trigger, m.Filename, statusError, m.DocumentMasterID, message)
	return err
}
