package consumer

import (
	"context"
	"errors"
	"fmt"
	"reflect"
	"strings"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/config"
)

type LegacyMessage struct {
	ID     string
	Values map[string]any
}

type LegacyStream interface {
	LastID(context.Context, string) (string, error)
	ReadAfter(context.Context, string, string) ([]LegacyMessage, error)
	SaveLastID(context.Context, string, string) error
}

type LegacyOptions struct {
	StreamKey     string
	CheckpointKey string
	StartID       string
	Workload      config.Workload
}

type Legacy struct {
	stream    LegacyStream
	processor DeliveryProcessor
	options   LegacyOptions
	wait      func(context.Context, time.Duration) error
}

func NewLegacy(stream LegacyStream, processor DeliveryProcessor, options LegacyOptions) *Legacy {
	return &Legacy{stream: stream, processor: processor, options: options, wait: waitLegacyBackoff}
}

func (l *Legacy) Run(ctx context.Context) (err error) {
	if ctx == nil {
		return errLegacy("context", context.Canceled, nil)
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if l == nil || isNilLegacy(l.stream) || isNilLegacy(l.processor) {
		return errLegacy("configuration", errors.New("legacy dependencies are required"), nil)
	}
	if err := validateLegacyOptions(l.options); err != nil {
		return err
	}
	lastID, err := l.lastID(ctx)
	if err != nil {
		return err
	}
	backoff := 250 * time.Millisecond
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		messages, readErr := l.readAfter(ctx, lastID)
		if readErr != nil {
			if ctxErr := ctx.Err(); ctxErr != nil {
				return ctxErr
			}
			return errLegacy("read", readErr, nil)
		}
		for _, message := range messages {
			if strings.TrimSpace(message.ID) == "" {
				return errLegacy("message", errors.New("legacy message identifier is required"), nil)
			}
			delivery, decodeErr := decodeLegacyMessage(message, l.options.Workload)
			if decodeErr != nil && delivery.Message.JobID <= 0 {
				return errLegacy("message", decodeErr, nil)
			}
			for {
				if err := ctx.Err(); err != nil {
					return err
				}
				processErr := decodeErr
				if processErr == nil {
					processErr = l.process(ctx, delivery)
				} else {
					// A correlated malformed message is deliberately offered to the
					// shared handler with only its job ID. It can persist invalid_message.
					processErr = l.process(ctx, delivery)
				}
				if processErr == nil {
					if err := l.save(ctx, message.ID); err != nil {
						if ctxErr := ctx.Err(); ctxErr != nil {
							return ctxErr
						}
						return errLegacy("checkpoint", err, nil)
					}
					lastID = message.ID
					backoff = 250 * time.Millisecond
					break
				}
				if ctxErr := ctx.Err(); ctxErr != nil {
					return ctxErr
				}
				if !compression.IsRetryable(processErr) {
					return errLegacy("process", processErr, nil)
				}
				if err := l.wait(ctx, backoff); err != nil {
					if ctxErr := ctx.Err(); ctxErr != nil {
						return ctxErr
					}
					return errLegacy("backoff", err, nil)
				}
				if backoff < 30*time.Second {
					backoff *= 2
					if backoff > 30*time.Second {
						backoff = 30 * time.Second
					}
				}
			}
		}
	}
}

func (l *Legacy) lastID(ctx context.Context) (id string, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = errLegacy("checkpoint", panicError(recovered), nil)
		}
	}()
	id, err = l.stream.LastID(ctx, l.options.CheckpointKey)
	if err != nil {
		return "", errLegacy("checkpoint", err, nil)
	}
	if strings.TrimSpace(id) == "" {
		return l.options.StartID, nil
	}
	return id, nil
}

func (l *Legacy) readAfter(ctx context.Context, id string) (messages []LegacyMessage, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = errLegacy("read", panicError(recovered), nil)
		}
	}()
	messages, err = l.stream.ReadAfter(ctx, l.options.StreamKey, id)
	if err != nil {
		return nil, errLegacy("read", err, nil)
	}
	return messages, nil
}

func (l *Legacy) save(ctx context.Context, id string) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = errLegacy("checkpoint", panicError(recovered), nil)
		}
	}()
	err = l.stream.SaveLastID(ctx, l.options.CheckpointKey, id)
	if err != nil {
		return errLegacy("checkpoint", err, nil)
	}
	return nil
}

func (l *Legacy) process(ctx context.Context, delivery compression.Delivery) (err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = panicError(recovered)
		}
	}()
	return l.processor.Process(ctx, delivery)
}

func validateLegacyOptions(options LegacyOptions) error {
	if strings.TrimSpace(options.StreamKey) == "" || strings.TrimSpace(options.CheckpointKey) == "" {
		return errLegacy("configuration", errors.New("legacy stream and checkpoint keys are required"), nil)
	}
	if options.StartID != "0" && options.StartID != "$" {
		return errLegacy("configuration", errors.New("legacy start identifier must be 0 or $"), nil)
	}
	if options.Workload != config.WorkloadNormal && options.Workload != config.WorkloadLarge {
		return errLegacy("configuration", errors.New("legacy workload is invalid"), nil)
	}
	return nil
}

func waitLegacyBackoff(ctx context.Context, duration time.Duration) error {
	timer := time.NewTimer(duration)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

type legacySafeError struct {
	operation string
	cause     error
}

func (e *legacySafeError) Error() string { return "legacy " + e.operation + " failed" }
func (e *legacySafeError) Unwrap() error { return e.cause }
func errLegacy(operation string, cause, _ error) error {
	if cause == nil {
		cause = errors.New("legacy operation failed")
	}
	if errors.Is(cause, context.Canceled) || errors.Is(cause, context.DeadlineExceeded) {
		return cause
	}
	return &legacySafeError{operation: operation, cause: cause}
}

type legacyPanicError struct{ cause error }

func (e *legacyPanicError) Error() string { return "legacy dependency panic" }
func (e *legacyPanicError) Unwrap() error { return e.cause }
func panicError(value any) error {
	if cause, ok := value.(error); ok {
		return &legacyPanicError{cause: cause}
	}
	return &legacyPanicError{cause: fmt.Errorf("legacy dependency panic value")}
}
func isNilLegacy(value any) bool {
	if value == nil {
		return true
	}
	v := reflect.ValueOf(value)
	switch v.Kind() {
	case reflect.Chan, reflect.Func, reflect.Interface, reflect.Map, reflect.Pointer, reflect.Slice:
		return v.IsNil()
	}
	return false
}
