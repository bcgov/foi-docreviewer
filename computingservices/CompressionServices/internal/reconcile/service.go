package reconcile

import (
	"context"
	"errors"
	"log/slog"
	"reflect"
	"time"

	"compressionservices/internal/config"
	"compressionservices/internal/store"
)

type Repository interface {
	ListStale(context.Context, store.Thresholds, int) ([]store.Job, error)
	WithinJobLock(context.Context, int, func(context.Context) error) (bool, error)
	Latest(context.Context, int) (store.Job, bool, error)
	Fail(context.Context, int, store.FailureCode) (store.Job, error)
}

type Summary struct {
	Scanned         int
	Locked          int
	AlreadyTerminal int
	Terminalized    int
	Failed          int
}

type Options struct {
	Thresholds          store.Thresholds
	BatchSize           int
	FinalizationTimeout time.Duration
}

type Service struct {
	repository Repository
	options    Options
	logger     *slog.Logger
	now        func() time.Time
}

func New(repository Repository, options Options, logger *slog.Logger) *Service {
	return &Service{repository: repository, options: options, logger: logger, now: time.Now}
}

func (s *Service) RunOnce(ctx context.Context) (summary Summary, err error) {
	if ctx == nil {
		return Summary{}, context.Canceled
	}
	if ctxErr := ctx.Err(); ctxErr != nil {
		return Summary{}, ctxErr
	}
	if s == nil || isNil(s.repository) || s.logger == nil {
		return Summary{}, errors.New("invalid reconciliation service")
	}
	if err := validateOptions(s.options); err != nil {
		return Summary{}, err
	}
	thresholds := s.options.Thresholds
	s.logger.Info("compression reconciliation started", "normal_after", thresholds.Normal.String(), "large_after", thresholds.Large.String(), "unknown_after", thresholds.Unknown.String(), "batch_size", s.options.BatchSize)
	defer func() {
		s.logger.Info("compression reconciliation completed", "scanned", summary.Scanned, "locked", summary.Locked, "already_terminal", summary.AlreadyTerminal, "terminalized", summary.Terminalized, "failed", summary.Failed)
	}()
	defer func() {
		if recovered := recover(); recovered != nil {
			err = errors.Join(err, safeJobError("reconciliation", panicAsError(recovered)))
			summary.Failed++
		}
	}()
	jobs, listErr := s.repository.ListStale(ctx, thresholds, s.options.BatchSize)
	if listErr != nil {
		return Summary{}, safeJobError("list", listErr)
	}
	summary.Scanned = len(jobs)
	for _, candidate := range jobs {
		if ctxErr := ctx.Err(); ctxErr != nil {
			return summary, ctxErr
		}
		if candidateErr := validateCandidate(candidate); candidateErr != nil {
			summary.Failed++
			wrapped := safeJobError("candidate", candidateErr)
			s.logger.Warn("compression reconciliation job failed", "job_id", candidate.JobID, "code", string(store.FailureCodeInvalidMessage))
			appendErr(&err, wrapped)
			continue
		}
		jobCtx, cancel := context.WithTimeout(ctx, s.options.FinalizationTimeout)
		locked, jobErr := s.reconcileLocked(jobCtx, candidate, &summary)
		if jobErr != nil && !locked {
			cancel()
			summary.Failed++
			wrapped := safeJobError("lock", jobErr)
			s.logger.Warn("compression reconciliation job failed", "job_id", candidate.JobID, "code", string(store.FailureCodeDatabaseUnavailable))
			appendErr(&err, wrapped)
			continue
		}
		if !locked {
			cancel()
			continue
		}
		summary.Locked++
		cancel()
		if jobErr != nil {
			summary.Failed++
			wrapped := safeJobError("job", jobErr)
			s.logger.Warn("compression reconciliation job failed", "job_id", candidate.JobID, "code", string(store.FailureCodeDatabaseUnavailable))
			appendErr(&err, wrapped)
		}
	}
	return summary, err
}

func (s *Service) reconcileLocked(ctx context.Context, candidate store.Job, summary *Summary) (locked bool, result error) {
	var latest store.Job
	var found bool
	var err error
	// WithinJobLock invokes the callback synchronously. Re-read under the lock.
	defer func() {
		if recovered := recover(); recovered != nil {
			result = panicAsError(recovered)
		}
	}()
	locked, lockErr := s.repository.WithinJobLock(ctx, candidate.JobID, func(lockCtx context.Context) error {
		latest, found, err = s.latest(lockCtx, candidate.JobID)
		if err != nil {
			return err
		}
		if ctxErr := lockCtx.Err(); ctxErr != nil {
			return ctxErr
		}
		if !found {
			return errors.New("latest job was not found")
		}
		if terminalJob(latest) {
			summary.AlreadyTerminal++
			return nil
		}
		if invalidLatest(latest, candidate.JobID) {
			return errors.New("latest job row is invalid")
		}
		if !s.isStale(latest) {
			return nil
		}
		stored, failErr := s.fail(lockCtx, candidate.JobID)
		if failErr != nil {
			return failErr
		}
		if stored.JobID != candidate.JobID || stored.Version != 3 {
			return errors.New("reconciliation failure was not confirmed")
		}
		if stored.Status == store.StatusCompleted || stored.Status == store.StatusSkipped {
			summary.AlreadyTerminal++
			return nil
		}
		if stored.Status != store.StatusError {
			return errors.New("reconciliation failure was not confirmed")
		}
		summary.Terminalized++
		return nil
	})
	if lockErr != nil {
		return locked, lockErr
	}
	if !locked {
		return false, nil
	}
	return true, err
}

func (s *Service) latest(ctx context.Context, jobID int) (job store.Job, found bool, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = panicAsError(recovered)
		}
	}()
	return s.repository.Latest(ctx, jobID)
}
func (s *Service) fail(ctx context.Context, jobID int) (job store.Job, err error) {
	defer func() {
		if recovered := recover(); recovered != nil {
			err = panicAsError(recovered)
		}
	}()
	return s.repository.Fail(ctx, jobID, store.FailureCodeStaleUnfinished)
}
func (s *Service) isStale(job store.Job) bool {
	age := s.now().Sub(job.CreatedAt)
	threshold := s.options.Thresholds.Unknown
	if job.WorkloadKnown {
		if job.Workload == config.WorkloadNormal {
			threshold = s.options.Thresholds.Normal
		} else if job.Workload == config.WorkloadLarge {
			threshold = s.options.Thresholds.Large
		}
	}
	return age >= threshold
}
func validateOptions(options Options) error {
	if options.Thresholds.Normal <= 0 || options.Thresholds.Large <= 0 || options.Thresholds.Unknown <= 0 || options.BatchSize <= 0 || options.FinalizationTimeout <= 0 {
		return errors.New("invalid reconciliation options")
	}
	return nil
}
func validateCandidate(job store.Job) error {
	if job.JobID <= 0 || (job.Version != 1 && job.Version != 2) || job.CreatedAt.IsZero() {
		return errors.New("candidate row is invalid")
	}
	if job.WorkloadKnown && job.Workload != config.WorkloadNormal && job.Workload != config.WorkloadLarge {
		return errors.New("candidate workload is invalid")
	}
	if job.Version == 1 && job.Status != store.StatusPushedToStream || job.Version == 2 && job.Status != store.StatusStarted {
		return errors.New("candidate status is invalid")
	}
	return nil
}
func invalidLatest(job store.Job, jobID int) bool {
	return job.JobID != jobID || job.CreatedAt.IsZero() || (job.Version != 1 && job.Version != 2) || (job.WorkloadKnown && job.Workload != config.WorkloadNormal && job.Workload != config.WorkloadLarge) || (job.Version == 1 && job.Status != store.StatusPushedToStream) || (job.Version == 2 && job.Status != store.StatusStarted)
}
func terminalJob(job store.Job) bool {
	return job.Version == 3 && (job.Status == store.StatusCompleted || job.Status == store.StatusSkipped || job.Status == store.StatusError)
}
func isNil(value any) bool {
	if value == nil {
		return true
	}
	v := reflect.ValueOf(value)
	switch v.Kind() {
	case reflect.Pointer, reflect.Interface, reflect.Map, reflect.Func, reflect.Slice, reflect.Chan:
		return v.IsNil()
	}
	return false
}

type safeError struct {
	operation string
	cause     error
}

func (e *safeError) Error() string { return "reconciliation " + e.operation + " failed" }
func (e *safeError) Unwrap() error { return e.cause }
func safeJobError(operation string, cause error) error {
	if cause == nil {
		cause = errors.New("reconciliation operation failed")
	}
	return &safeError{operation: operation, cause: cause}
}

type panicSafeError struct{ cause error }

func (e *panicSafeError) Error() string { return "reconciliation dependency panic" }
func (e *panicSafeError) Unwrap() error { return e.cause }
func panicAsError(value any) error {
	if cause, ok := value.(error); ok {
		return &panicSafeError{cause: cause}
	}
	return &panicSafeError{cause: errors.New("reconciliation dependency panic")}
}
func appendErr(target *error, next error) { *target = errors.Join(*target, next) }
