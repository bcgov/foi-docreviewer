package compression

import (
	"context"
	"errors"
	"log/slog"
	"reflect"
	"time"

	"compressionservices/internal/config"
	"compressionservices/internal/store"
	"compressionservices/models"
)

var (
	errInvalidHandler           = errors.New("invalid compression handler")
	errInvalidJobID             = errors.New("invalid compression job identifier")
	errInvalidProcessorResult   = errors.New("invalid compression processor result")
	errLockContended            = errors.New("compression job lock contended")
	errTerminalStateUnconfirmed = errors.New("compression terminal state is unconfirmed")
)

type Handler struct {
	repository Repository
	processor  Processor
	followUp   FollowUp
	options    Options
	logger     *slog.Logger
}

func NewHandler(
	repository Repository,
	processor Processor,
	followUp FollowUp,
	options Options,
) *Handler {
	if options.Now == nil {
		options.Now = time.Now
	}
	logger := options.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &Handler{
		repository: repository,
		processor:  processor,
		followUp:   followUp,
		options:    options,
		logger:     logger,
	}
}

func (h *Handler) Process(ctx context.Context, delivery Delivery) (err error) {
	start := time.Now()

	defer func() {
		if recovered := recover(); recovered != nil {
			err = NewRetryableFailure(
				store.FailureCodeCompressionPanic,
				panicAsError(recovered),
			)
		}
	}()

	if ctx == nil {
		return NewRetryableFailure(store.FailureCodeInvalidMessage, errInvalidHandler)
	}
	if h == nil || isNilInterface(h.repository) || isNilInterface(h.processor) {
		return NewRetryableFailure(store.FailureCodeInvalidMessage, errInvalidHandler)
	}
	if delivery.Message.JobID <= 0 {
		return NewRetryableFailure(store.FailureCodeInvalidMessage, errInvalidJobID)
	}
	if !validWorkload(h.options.Workload) ||
		h.options.ProcessingTimeout <= 0 ||
		h.options.FinalizationTimeout <= 0 {
		return NewRetryableFailure(store.FailureCodeInvalidMessage, errInvalidHandler)
	}

	h.logger.Info("message_received",
		"job_id", delivery.Message.JobID,
		"request_number", delivery.Message.RequestNumber,
		"filename", delivery.Message.Filename,
		"document_master_id", delivery.Message.DocumentMasterID,
		"ministry_request_id", delivery.Message.MinistryRequestID,
		"workload", string(h.options.Workload),
	)

	callbackInvoked := false
	acquired, lockErr := h.repository.WithinJobLock(
		ctx,
		delivery.Message.JobID,
		func(lockCtx context.Context) error {
			callbackInvoked = true
			return h.processLocked(lockCtx, delivery, start)
		},
	)
	if lockErr != nil {
		return retryFrom(lockErr, store.FailureCodeDatabaseUnavailable)
	}
	if !acquired {
		h.logger.Debug("lock_contended", "job_id", delivery.Message.JobID)
		return NewRetryableFailure(store.FailureCodeDatabaseUnavailable, errLockContended)
	}
	if !callbackInvoked {
		return NewRetryableFailure(
			store.FailureCodeDatabaseUnavailable,
			errTerminalStateUnconfirmed,
		)
	}
	return nil
}

func (h *Handler) processLocked(ctx context.Context, delivery Delivery, start time.Time) error {
	latest, found, err := h.repository.Latest(ctx, delivery.Message.JobID)
	if err != nil {
		return NewRetryableFailure(store.FailureCodeDatabaseUnavailable, err)
	}
	if found && latest.Version == 3 {
		if !confirmedTerminal(latest, delivery.Message.JobID) {
			return NewRetryableFailure(
				store.FailureCodeTerminalStatePersistFailed,
				errTerminalStateUnconfirmed,
			)
		}
		h.afterConfirmedTerminal(ctx, delivery.Message, terminalResult(latest.Status))
		h.logCompleted(latest.Status, delivery.Message, start)
		return nil
	}
	if !preStartWorkloadMatches(h.options.Workload, delivery.Workload, latest, found) {
		h.logger.Warn("workload_mismatch",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeWorkloadMismatch),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeWorkloadMismatch,
			NewDeterministicFailure(store.FailureCodeWorkloadMismatch, nil),
		)
	}

	started, err := h.repository.EnsureStarted(ctx, delivery.Message, h.options.Workload)
	if err != nil {
		return NewRetryableFailure(store.FailureCodeDatabaseUnavailable, err)
	}
	if started.JobID != delivery.Message.JobID ||
		started.Version != 2 ||
		started.Status != store.StatusStarted ||
		started.CreatedAt.IsZero() {
		return NewRetryableFailure(store.FailureCodeDatabaseUnavailable, errTerminalStateUnconfirmed)
	}
	if !startedWorkloadMatches(h.options.Workload, delivery.Workload, started) {
		h.logger.Warn("workload_mismatch",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeWorkloadMismatch),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeWorkloadMismatch,
			NewDeterministicFailure(store.FailureCodeWorkloadMismatch, nil),
		)
	}

	h.logger.Info("compression_started",
		"job_id", delivery.Message.JobID,
		"filename", delivery.Message.Filename,
		"workload", string(h.options.Workload),
	)

	deadline := started.CreatedAt.Add(h.options.ProcessingTimeout)
	interruption, interruptionErr := h.classifyInterruption(ctx, nil, deadline)
	switch interruption {
	case interruptionCaller:
		return retryFrom(interruptionErr, store.FailureCodeDatabaseUnavailable)
	case interruptionJobDeadline:
		h.logger.Warn("compression_timeout",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeCompressionTimeout),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeCompressionTimeout,
			interruptionErr,
		)
	}

	processingCtx, cancel := context.WithDeadline(ctx, deadline)
	defer cancel()

	result, processingErr, processingPanic := h.compress(processingCtx, delivery.Message)
	if processingPanic != nil {
		h.logger.Error("compression_failed",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeCompressionPanic),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeCompressionPanic,
			processingPanic,
		)
	}
	interruption, interruptionErr = h.classifyInterruption(ctx, processingCtx, deadline)
	if interruption == interruptionJobDeadline {
		h.logger.Warn("compression_timeout",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeCompressionTimeout),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeCompressionTimeout,
			errors.Join(processingErr, interruptionErr),
		)
	}
	if interruption == interruptionCaller {
		return retryFrom(
			errors.Join(processingErr, interruptionErr),
			store.FailureCodeDatabaseUnavailable,
		)
	}
	if processingErr != nil {
		if failure, ok := asFailure(processingErr); ok && !failure.Retryable {
			h.logger.Error("compression_failed",
				"job_id", delivery.Message.JobID,
				"failure_code", string(failure.Code),
			)
			return h.persistFailure(
				ctx,
				delivery,
				store.FailureCode(failure.Error()),
				processingErr,
			)
		}
		resolvedCode := store.FailureCodeDatabaseUnavailable
		if failure, ok := asFailure(processingErr); ok && failure.Retryable {
			resolvedCode = store.FailureCode(failure.Error())
		}
		h.logger.Warn("compression_failed",
			"job_id", delivery.Message.JobID,
			"failure_code", string(resolvedCode),
		)
		return NewRetryableFailure(resolvedCode, processingErr)
	}
	if result.Status != store.StatusCompleted && result.Status != store.StatusSkipped {
		h.logger.Error("compression_failed",
			"job_id", delivery.Message.JobID,
			"failure_code", string(store.FailureCodeInvalidMessage),
		)
		return h.persistFailure(
			ctx,
			delivery,
			store.FailureCodeInvalidMessage,
			errInvalidProcessorResult,
		)
	}

	stored, completeErr := h.complete(processingCtx, delivery.Message, result)
	if confirmedTerminal(stored, delivery.Message.JobID) {
		if stored.Status == store.StatusCompleted || stored.Status == store.StatusSkipped {
			confirmedResult := result
			if stored.Status != result.Status {
				confirmedResult = terminalResult(stored.Status)
			}
			h.afterConfirmedTerminal(ctx, delivery.Message, confirmedResult)
			h.logCompleted(stored.Status, delivery.Message, start)
		}
		return nil
	}
	if completeErr != nil {
		contextInterrupted := processingCtx.Err() != nil ||
			errors.Is(completeErr, context.Canceled) ||
			errors.Is(completeErr, context.DeadlineExceeded)
		if contextInterrupted {
			interruption, interruptionErr = h.classifyInterruption(ctx, processingCtx, deadline)
			if interruption == interruptionJobDeadline {
				h.logger.Warn("compression_timeout",
					"job_id", delivery.Message.JobID,
					"failure_code", string(store.FailureCodeCompressionTimeout),
				)
				return h.persistFailure(
					ctx,
					delivery,
					store.FailureCodeCompressionTimeout,
					errors.Join(completeErr, interruptionErr),
				)
			}
		}
		return NewRetryableFailure(
			store.FailureCodeTerminalStatePersistFailed,
			errors.Join(completeErr, interruptionErr),
		)
	}
	return NewRetryableFailure(
		store.FailureCodeTerminalStatePersistFailed,
		errTerminalStateUnconfirmed,
	)
}

// logCompleted emits completion events for successful terminal states only.
func (h *Handler) logCompleted(status string, message models.CompressionProducerMessage, start time.Time) {
	switch status {
	case store.StatusSkipped:
		h.logger.Info("compression_skipped",
			"job_id", message.JobID,
			"filename", message.Filename,
		)
	case store.StatusCompleted:
		h.logger.Info("compression_completed",
			"job_id", message.JobID,
			"filename", message.Filename,
		)
	default:
		return
	}
	h.logger.Info("message_completed",
		"job_id", message.JobID,
		"filename", message.Filename,
		"duration_ms", time.Since(start).Milliseconds(),
	)
}

func (h *Handler) compress(
	ctx context.Context,
	message models.CompressionProducerMessage,
) (result store.CompressionResult, err error, panicErr error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			panicErr = panicAsError(recovered)
		}
	}()
	result, err = h.processor.Compress(ctx, message)
	return result, err, nil
}

func (h *Handler) persistFailure(
	ctx context.Context,
	delivery Delivery,
	code store.FailureCode,
	trigger error,
) error {
	finalizationCtx, cancel := context.WithTimeout(
		context.WithoutCancel(ctx),
		h.options.FinalizationTimeout,
	)
	defer cancel()

	stored, err := h.fail(finalizationCtx, delivery.Message.JobID, code)
	if err != nil {
		return NewRetryableFailure(
			store.FailureCodeTerminalStatePersistFailed,
			errors.Join(trigger, err),
		)
	}
	if !confirmedTerminal(stored, delivery.Message.JobID) {
		return NewRetryableFailure(
			store.FailureCodeTerminalStatePersistFailed,
			errors.Join(trigger, errTerminalStateUnconfirmed),
		)
	}
	if stored.Status == store.StatusCompleted || stored.Status == store.StatusSkipped {
		h.afterConfirmedTerminal(
			ctx,
			delivery.Message,
			terminalResult(stored.Status),
		)
	}
	return nil
}

func (h *Handler) complete(
	ctx context.Context,
	message models.CompressionProducerMessage,
	result store.CompressionResult,
) (job store.Job, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = panicAsError(recovered)
		}
	}()
	return h.repository.Complete(ctx, message, result)
}

func (h *Handler) fail(
	ctx context.Context,
	jobID int,
	code store.FailureCode,
) (job store.Job, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = panicAsError(recovered)
		}
	}()
	return h.repository.Fail(ctx, jobID, code)
}

func (h *Handler) afterConfirmedTerminal(
	ctx context.Context,
	message models.CompressionProducerMessage,
	result store.CompressionResult,
) {
	if result.Status != store.StatusCompleted && result.Status != store.StatusSkipped {
		return
	}
	if isNilInterface(h.followUp) {
		return
	}
	defer func() {
		_ = recover()
	}()
	h.followUp.AfterTerminal(ctx, message, result)
	h.logger.Info("ocr_published", "job_id", message.JobID)
}

func retryFrom(err error, fallback store.FailureCode) error {
	code := fallback
	if failure, ok := asFailure(err); ok && failure.Retryable {
		code = store.FailureCode(failure.Error())
	}
	return NewRetryableFailure(code, err)
}

func preStartWorkloadMatches(
	configured config.Workload,
	delivered config.Workload,
	job store.Job,
	found bool,
) bool {
	if delivered != configured {
		return false
	}
	if !found {
		return true
	}
	if !job.WorkloadKnown {
		return job.Version == 1
	}
	return job.Workload == configured
}

func startedWorkloadMatches(
	configured config.Workload,
	delivered config.Workload,
	job store.Job,
) bool {
	return delivered == configured && job.WorkloadKnown && job.Workload == configured
}

func validWorkload(workload config.Workload) bool {
	return workload == config.WorkloadNormal || workload == config.WorkloadLarge
}

func confirmedTerminal(job store.Job, jobID int) bool {
	if job.JobID != jobID || job.Version != 3 {
		return false
	}
	switch job.Status {
	case store.StatusCompleted, store.StatusSkipped, store.StatusError:
		return true
	default:
		return false
	}
}

func terminalResult(status string) store.CompressionResult {
	return store.CompressionResult{Status: status}
}

func isNilInterface(value any) bool {
	if value == nil {
		return true
	}
	reflected := reflect.ValueOf(value)
	switch reflected.Kind() {
	case reflect.Chan,
		reflect.Func,
		reflect.Interface,
		reflect.Map,
		reflect.Pointer,
		reflect.Slice:
		return reflected.IsNil()
	default:
		return false
	}
}

type recoveredPanicError struct {
	cause error
	value any
}

func (e recoveredPanicError) Error() string {
	return "panic recovered"
}

func (e recoveredPanicError) Unwrap() error {
	return e.cause
}

func (e recoveredPanicError) PanicValue() any {
	return e.value
}

func panicAsError(recovered any) error {
	if cause, ok := recovered.(error); ok && !isNilInterface(cause) {
		return recoveredPanicError{cause: cause, value: recovered}
	}
	return recoveredPanicError{value: recovered}
}

type interruptionKind uint8

const (
	interruptionNone interruptionKind = iota
	interruptionCaller
	interruptionJobDeadline
)

func (h *Handler) classifyInterruption(
	parentCtx context.Context,
	processingCtx context.Context,
	jobDeadline time.Time,
) (interruptionKind, error) {
	parentErr := parentCtx.Err()
	if earlierCallerDeadlineWins(parentCtx, parentErr, jobDeadline) {
		return interruptionCaller, parentErr
	}

	var processingErr error
	if processingCtx != nil {
		processingErr = processingCtx.Err()
	}
	if errors.Is(processingErr, context.Canceled) {
		return interruptionCaller, errors.Join(parentErr, processingErr)
	}
	if errors.Is(processingErr, context.DeadlineExceeded) {
		return interruptionJobDeadline, errors.Join(context.DeadlineExceeded, processingErr)
	}
	if errors.Is(parentErr, context.Canceled) {
		return interruptionCaller, parentErr
	}
	if !h.options.Now().Before(jobDeadline) {
		return interruptionJobDeadline, context.DeadlineExceeded
	}
	if parentErr != nil {
		return interruptionCaller, parentErr
	}
	if processingErr != nil {
		return interruptionCaller, processingErr
	}
	return interruptionNone, nil
}

func earlierCallerDeadlineWins(
	parentCtx context.Context,
	parentErr error,
	jobDeadline time.Time,
) bool {
	if !errors.Is(parentErr, context.DeadlineExceeded) {
		return false
	}
	parentDeadline, ok := parentCtx.Deadline()
	return ok && parentDeadline.Before(jobDeadline)
}
