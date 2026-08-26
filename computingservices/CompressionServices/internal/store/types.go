// Package store persists compression job state in PostgreSQL.
package store

import (
	"errors"
	"time"

	"compressionservices/internal/config"
)

const (
	StatusPushedToStream = "pushedtostream"
	StatusStarted        = "started"
	StatusCompleted      = "completed"
	StatusSkipped        = "skipped"
	StatusError          = "error"
)

// FailureCode is the bounded vocabulary allowed in CompressionJob.message.
type FailureCode string

const (
	FailureCodeS3DownloadTimeout          FailureCode = "s3_download_timeout"
	FailureCodeS3UploadFailed             FailureCode = "s3_upload_failed"
	FailureCodeGhostscriptTimeout         FailureCode = "ghostscript_timeout"
	FailureCodeUnsupportedDocument        FailureCode = "unsupported_document"
	FailureCodeDatabaseUnavailable        FailureCode = "database_unavailable"
	FailureCodeTerminalStatePersistFailed FailureCode = "terminal_state_persist_failed"
	FailureCodeWorkloadMismatch           FailureCode = "workload_mismatch"
	FailureCodeStaleUnfinished            FailureCode = "stale_unfinished"
	FailureCodeCompressionTimeout         FailureCode = "compression_timeout"
	FailureCodeCompressionPanic           FailureCode = "compression_panic"
	FailureCodeInvalidMessage             FailureCode = "invalid_message"
)

var (
	ErrCompressedSizeOutOfRange = errors.New("compressed size is outside the database integer range")
	ErrCredentialsInvalid       = errors.New("credentials_invalid")
	ErrCredentialsNotFound      = errors.New("credentials_not_found")
	ErrInvalidFailureCode       = errors.New("invalid failure code")
	ErrInvalidLimit             = errors.New("limit must be positive")
	ErrInvalidTerminalStatus    = errors.New("terminal status must be completed or skipped")
	ErrInvalidThreshold         = errors.New("stale thresholds must be positive")
	ErrJobNotFound              = errors.New("compression job not found")
	ErrLockNotReleased          = errors.New("advisory lock was not released")
)

type Job struct {
	JobID         int
	Version       int
	Status        string
	Workload      config.Workload
	WorkloadKnown bool
	CreatedAt     time.Time
}

type CompressionResult struct {
	Status         string
	CompressedPath string
	CompressedSize int64
	Extension      string
}

type Thresholds struct {
	Normal  time.Duration
	Large   time.Duration
	Unknown time.Duration
}

type Options struct {
	OperationTimeout time.Duration
}

func validFailureCode(code FailureCode) bool {
	switch code {
	case FailureCodeS3DownloadTimeout,
		FailureCodeS3UploadFailed,
		FailureCodeGhostscriptTimeout,
		FailureCodeUnsupportedDocument,
		FailureCodeDatabaseUnavailable,
		FailureCodeTerminalStatePersistFailed,
		FailureCodeWorkloadMismatch,
		FailureCodeStaleUnfinished,
		FailureCodeCompressionTimeout,
		FailureCodeCompressionPanic,
		FailureCodeInvalidMessage:
		return true
	default:
		return false
	}
}
