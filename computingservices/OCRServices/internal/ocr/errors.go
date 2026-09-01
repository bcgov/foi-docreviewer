package ocr

import "errors"

type classifiedError struct {
	permanent bool
	err       error
}

func (e *classifiedError) Error() string {
	if e.permanent {
		return "permanent_handler_error"
	}
	return "retryable_handler_error"
}
func (e *classifiedError) Unwrap() error { return e.err }

// Retryable marks err as a transient failure eligible for redelivery.
func Retryable(err error) error {
	if err == nil {
		return nil
	}
	return &classifiedError{permanent: false, err: err}
}

// Permanent marks err as non-retryable (dead-letter on the consumer boundary).
func Permanent(err error) error {
	if err == nil {
		return nil
	}
	return &classifiedError{permanent: true, err: err}
}

// IsPermanent reports whether err was classified permanent.
func IsPermanent(err error) bool {
	var c *classifiedError
	return errors.As(err, &c) && c.permanent
}
