package compression

import (
	"errors"

	"compressionservices/internal/store"
)

// Failure is safe to return across transport boundaries. Its cause remains
// available for internal classification without entering Error output.
type Failure struct {
	Code      string
	Retryable bool
	cause     error
}

func (f *Failure) Error() string {
	if f == nil {
		return string(store.FailureCodeInvalidMessage)
	}
	fallback := store.FailureCodeInvalidMessage
	if f.Retryable {
		fallback = store.FailureCodeDatabaseUnavailable
	}
	return string(safeFailureCode(store.FailureCode(f.Code), fallback))
}

func (f *Failure) Unwrap() error {
	if f == nil {
		return nil
	}
	return f.cause
}

func NewDeterministicFailure(code store.FailureCode, cause error) *Failure {
	return &Failure{
		Code:      string(safeFailureCode(code, store.FailureCodeInvalidMessage)),
		Retryable: false,
		cause:     cause,
	}
}

func NewRetryableFailure(code store.FailureCode, cause error) *Failure {
	return &Failure{
		Code:      string(safeFailureCode(code, store.FailureCodeDatabaseUnavailable)),
		Retryable: true,
		cause:     cause,
	}
}

func IsDeterministic(err error) bool {
	failure, ok := asFailure(err)
	return ok && !failure.Retryable
}

func IsRetryable(err error) bool {
	failure, ok := asFailure(err)
	return ok && failure.Retryable
}

func asFailure(err error) (*Failure, bool) {
	var failure *Failure
	if !errors.As(err, &failure) {
		return nil, false
	}
	if failure == nil {
		return &Failure{
			Code:      string(store.FailureCodeInvalidMessage),
			Retryable: true,
		}, true
	}
	return failure, true
}

func safeFailureCode(code, fallback store.FailureCode) store.FailureCode {
	switch code {
	case store.FailureCodeS3DownloadTimeout,
		store.FailureCodeS3UploadFailed,
		store.FailureCodeGhostscriptTimeout,
		store.FailureCodeUnsupportedDocument,
		store.FailureCodeDatabaseUnavailable,
		store.FailureCodeTerminalStatePersistFailed,
		store.FailureCodeWorkloadMismatch,
		store.FailureCodeStaleUnfinished,
		store.FailureCodeCompressionTimeout,
		store.FailureCodeCompressionPanic,
		store.FailureCodeInvalidMessage:
		return code
	default:
		return fallback
	}
}
