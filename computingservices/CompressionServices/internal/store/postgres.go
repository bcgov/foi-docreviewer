package store

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"os"
	"strings"

	"compressionservices/internal/config"
	"compressionservices/models"
)

const advisoryNamespace int32 = 5199

const selectJobColumns = `
	SELECT compressionjobid, version, status, workload, createdat
	FROM public."CompressionJob"`

const selectStoredJobColumns = `
	SELECT compressionjobid, version, status, workload, createdat, documentmasterid, ministryrequestid
	FROM public."CompressionJob"`

type Repository struct {
	db      *sql.DB
	options Options
}

func New(db *sql.DB, options Options) *Repository {
	return &Repository{db: db, options: options}
}

func (r *Repository) WithinJobLock(
	ctx context.Context,
	jobID int,
	callback func(context.Context) error,
) (acquired bool, err error) {
	connectionCtx, connectionCancel := r.operationContext(ctx)
	conn, err := r.db.Conn(connectionCtx)
	connectionErr := databaseError(connectionCtx, "acquiring advisory lock connection", err)
	connectionCancel()
	if err != nil {
		return false, connectionErr
	}
	defer func() {
		if closeErr := conn.Close(); closeErr != nil && !errors.Is(closeErr, sql.ErrConnDone) {
			err = errors.Join(err, fmt.Errorf("closing advisory lock connection: %w", closeErr))
		}
	}()

	lockCtx, lockCancel := r.operationContext(ctx)
	lockErr := conn.QueryRowContext(
		lockCtx,
		`SELECT pg_try_advisory_lock($1, $2)`,
		advisoryNamespace,
		jobID,
	).Scan(&acquired)
	lockErr = databaseError(lockCtx, "acquiring advisory lock", lockErr)
	lockCancel()
	if lockErr != nil {
		return false, lockErr
	}
	if !acquired {
		return false, nil
	}

	defer func() {
		unlockCtx, unlockCancel := r.cleanupContext(ctx)
		defer unlockCancel()

		var unlocked bool
		unlockErr := conn.QueryRowContext(
			unlockCtx,
			`SELECT pg_advisory_unlock($1, $2)`,
			advisoryNamespace,
			jobID,
		).Scan(&unlocked)
		if unlockErr != nil {
			err = errors.Join(
				err,
				databaseError(unlockCtx, "releasing advisory lock", unlockErr),
				discardConnection(conn),
			)
			return
		}
		if !unlocked {
			err = errors.Join(err, ErrLockNotReleased, discardConnection(conn))
		}
	}()

	return true, callback(ctx)
}

func discardConnection(conn *sql.Conn) error {
	err := conn.Raw(func(any) error {
		return driver.ErrBadConn
	})
	if errors.Is(err, driver.ErrBadConn) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("discarding advisory lock connection: %w", err)
	}
	return nil
}

func (r *Repository) Latest(ctx context.Context, jobID int) (Job, bool, error) {
	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	job, err := queryJob(
		operationCtx,
		r.db,
		selectJobColumns+`
		WHERE compressionjobid = $1
		ORDER BY version DESC
		LIMIT 1`,
		jobID,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return Job{}, false, nil
	}
	if err != nil {
		return Job{}, false, databaseError(operationCtx, "querying latest compression job", err)
	}
	return job, true, nil
}

func (r *Repository) EnsureStarted(
	ctx context.Context,
	message models.CompressionProducerMessage,
	workload config.Workload,
) (Job, error) {
	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	_, err := r.db.ExecContext(operationCtx, `
		INSERT INTO public."CompressionJob"
		(compressionjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, workload)
		SELECT compressionjobid, 2, ministryrequestid, batch, trigger, filename, $3, documentmasterid,
			COALESCE(workload, $2)
		FROM public."CompressionJob"
		WHERE compressionjobid = $1 AND version = 1
		ON CONFLICT (compressionjobid, version) DO NOTHING`,
		message.JobID,
		workload,
		StatusStarted,
	)
	if err != nil {
		return Job{}, databaseError(operationCtx, "inserting compression job start", err)
	}

	job, err := queryJob(
		operationCtx,
		r.db,
		selectJobColumns+`
		WHERE compressionjobid = $1 AND version = 2`,
		message.JobID,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return Job{}, ErrJobNotFound
	}
	if err != nil {
		return Job{}, databaseError(operationCtx, "querying compression job start", err)
	}
	return job, nil
}

func (r *Repository) Complete(
	ctx context.Context,
	message models.CompressionProducerMessage,
	result CompressionResult,
) (job Job, err error) {
	if result.Status != StatusCompleted && result.Status != StatusSkipped {
		return Job{}, ErrInvalidTerminalStatus
	}
	if result.Status == StatusCompleted && (result.CompressedSize > math.MaxInt32 || result.CompressedSize < math.MinInt32) {
		return Job{}, ErrCompressedSizeOutOfRange
	}

	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	tx, err := r.db.BeginTx(operationCtx, nil)
	if err != nil {
		return Job{}, databaseError(operationCtx, "beginning compression completion transaction", err)
	}
	committed := false
	defer func() {
		if committed {
			return
		}
		if rollbackErr := tx.Rollback(); rollbackErr != nil && !errors.Is(rollbackErr, sql.ErrTxDone) {
			err = errors.Join(
				err,
				databaseError(operationCtx, "rolling back compression completion", rollbackErr),
			)
		}
	}()

	stored, err := queryStoredJob(
		operationCtx,
		tx,
		selectStoredJobColumns+`
		WHERE compressionjobid = $1 AND version = 3`,
		message.JobID,
	)
	if err == nil {
		if err := tx.Commit(); err != nil {
			return Job{}, databaseError(operationCtx, "committing existing compression completion", err)
		}
		committed = true
		return stored.Job, nil
	}
	if !errors.Is(err, sql.ErrNoRows) {
		return Job{}, databaseError(operationCtx, "querying existing compression completion", err)
	}

	_, err = tx.ExecContext(operationCtx, `
		INSERT INTO public."CompressionJob"
		(compressionjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, workload)
		SELECT compressionjobid, 3, ministryrequestid, batch, trigger, filename, $2, documentmasterid, workload
		FROM public."CompressionJob"
		WHERE compressionjobid = $1
		ORDER BY version DESC
		LIMIT 1
		ON CONFLICT (compressionjobid, version) DO NOTHING`,
		message.JobID,
		result.Status,
	)
	if err != nil {
		return Job{}, databaseError(operationCtx, "inserting compression completion", err)
	}

	stored, err = queryStoredJob(
		operationCtx,
		tx,
		selectStoredJobColumns+`
		WHERE compressionjobid = $1 AND version = 3`,
		message.JobID,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return Job{}, ErrJobNotFound
	}
	if err != nil {
		return Job{}, databaseError(operationCtx, "querying stored compression completion", err)
	}

	if stored.Status == result.Status {
		if err := updateDocumentAttributes(operationCtx, tx, stored, result); err != nil {
			return Job{}, err
		}
		if err := updateDocumentMaster(operationCtx, tx, stored, result); err != nil {
			return Job{}, err
		}
	}

	if err := tx.Commit(); err != nil {
		return Job{}, databaseError(operationCtx, "committing compression completion", err)
	}
	committed = true
	return stored.Job, nil
}

func (r *Repository) Fail(ctx context.Context, jobID int, code FailureCode) (Job, error) {
	if !validFailureCode(code) {
		return Job{}, ErrInvalidFailureCode
	}

	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	_, err := r.db.ExecContext(operationCtx, `
		INSERT INTO public."CompressionJob"
		(compressionjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, message, workload)
		SELECT compressionjobid, 3, ministryrequestid, batch, trigger, filename, $2, documentmasterid, $3, workload
		FROM public."CompressionJob"
		WHERE compressionjobid = $1
		ORDER BY version DESC
		LIMIT 1
		ON CONFLICT (compressionjobid, version) DO NOTHING`,
		jobID,
		StatusError,
		code,
	)
	if err != nil {
		return Job{}, databaseError(operationCtx, "inserting compression failure", err)
	}

	job, err := queryJob(
		operationCtx,
		r.db,
		selectJobColumns+`
		WHERE compressionjobid = $1 AND version = 3`,
		jobID,
	)
	if errors.Is(err, sql.ErrNoRows) {
		return Job{}, ErrJobNotFound
	}
	if err != nil {
		return Job{}, databaseError(operationCtx, "querying stored compression failure", err)
	}
	return job, nil
}

func (r *Repository) ListStale(
	ctx context.Context,
	thresholds Thresholds,
	limit int,
) (jobs []Job, err error) {
	if limit <= 0 {
		return nil, ErrInvalidLimit
	}
	if thresholds.Normal <= 0 || thresholds.Large <= 0 || thresholds.Unknown <= 0 {
		return nil, ErrInvalidThreshold
	}

	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	rows, err := r.db.QueryContext(operationCtx, `
		SELECT compressionjobid, version, status, workload, createdat
		FROM (
			SELECT DISTINCT ON (compressionjobid)
				compressionjobid, version, status, workload, createdat
			FROM public."CompressionJob"
			ORDER BY compressionjobid, version DESC
		) latest
		WHERE version IN (1, 2)
		AND createdat <= now() - CASE workload
			WHEN 'normal' THEN make_interval(secs => $1)
			WHEN 'large' THEN make_interval(secs => $2)
			ELSE make_interval(secs => $3)
		END
		ORDER BY createdat, compressionjobid
		LIMIT $4`,
		thresholds.Normal.Seconds(),
		thresholds.Large.Seconds(),
		thresholds.Unknown.Seconds(),
		limit,
	)
	if err != nil {
		return nil, databaseError(operationCtx, "querying stale compression jobs", err)
	}
	defer func() {
		if closeErr := rows.Close(); closeErr != nil {
			err = errors.Join(
				err,
				databaseError(operationCtx, "closing stale compression job rows", closeErr),
			)
		}
	}()

	jobs = []Job{}
	for rows.Next() {
		job, scanErr := scanJob(rows)
		if scanErr != nil {
			return nil, databaseError(operationCtx, "scanning stale compression job", scanErr)
		}
		jobs = append(jobs, job)
	}
	if err := rows.Err(); err != nil {
		return nil, databaseError(operationCtx, "iterating stale compression jobs", err)
	}
	if err := rows.Close(); err != nil {
		return nil, databaseError(operationCtx, "closing stale compression job rows", err)
	}
	return jobs, nil
}

func (r *Repository) Credentials(
	ctx context.Context,
	bcgovCode string,
) (models.S3Credentials, string, error) {
	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	bucket := fmt.Sprintf(
		"%s-%s-e",
		strings.ToLower(bcgovCode),
		strings.ToLower(os.Getenv("COMPRESSION_S3_ENV")),
	)
	var attributes sql.NullString
	err := r.db.QueryRowContext(operationCtx, `
		SELECT attributes
		FROM public."DocumentPathMapper"
		WHERE bucket = $1 AND category = 'Records'`,
		bucket,
	).Scan(&attributes)
	if errors.Is(err, sql.ErrNoRows) {
		return models.S3Credentials{}, "", ErrCredentialsNotFound
	}
	if err != nil {
		return models.S3Credentials{}, "", credentialError{
			cause: databaseError(operationCtx, "querying credentials", err),
		}
	}
	if !attributes.Valid {
		return models.S3Credentials{}, "", ErrCredentialsInvalid
	}

	var credentials models.S3Credentials
	if err := json.Unmarshal([]byte(attributes.String), &credentials); err != nil {
		return models.S3Credentials{}, "", credentialError{cause: err, invalid: true}
	}
	return credentials, bucket, nil
}

func (r *Repository) EnsureOCRStarted(
	ctx context.Context,
	message models.CompressionProducerMessage,
) (int, error) {
	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	_, err := r.db.ExecContext(operationCtx, `
		INSERT INTO public."OCRActiveMQJob"
		(ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (ocractivemqjobid, version) DO NOTHING`,
		message.JobID,
		1,
		message.MinistryRequestID,
		message.Batch,
		message.Trigger,
		message.Filename,
		StatusPushedToStream,
		message.DocumentMasterID,
	)
	if err != nil {
		return 0, databaseError(operationCtx, "ensuring OCR job start", err)
	}
	return message.JobID, nil
}

func (r *Repository) UpdateRedactionReady(
	ctx context.Context,
	message models.CompressionProducerMessage,
) error {
	operationCtx, cancel := r.operationContext(ctx)
	defer cancel()

	_, err := r.db.ExecContext(operationCtx, `
		UPDATE "DocumentMaster" dm
		SET isredactionready = true,
			updatedby = 'compressionservice',
			updated_at = now()
		FROM (
			SELECT DISTINCT ON (documentmasterid) documentmasterid, version, status
			FROM "CompressionJob"
			WHERE ministryrequestid = $1
			ORDER BY documentmasterid, version DESC
		) AS sq
		WHERE dm.documentmasterid = sq.documentmasterid
		AND dm.isredactionready = false
		AND sq.status = 'completed'
		AND dm.ministryrequestid = $1`,
		message.MinistryRequestID,
	)
	if err != nil {
		return databaseError(operationCtx, "updating redaction-ready state", err)
	}
	return nil
}

func updateDocumentAttributes(
	ctx context.Context,
	tx *sql.Tx,
	stored storedJob,
	result CompressionResult,
) error {
	compressedSize := sql.NullInt64{Valid: false}
	if result.Status == StatusCompleted {
		compressedSize = sql.NullInt64{Int64: result.CompressedSize, Valid: true}
	}
	_, err := tx.ExecContext(ctx, `
		UPDATE "DocumentAttributes" da
		SET attributes = (attributes::jsonb || jsonb_build_object('compressedfilesize', $2::integer))::json
		WHERE da.documentmasterid = $1::integer
		AND da.isactive = true
		AND EXISTS (
			SELECT 1
			FROM "CompressionJob" cj
			WHERE cj.compressionjobid = $3
			AND cj.version = 3
			AND cj.status = $4
			AND cj.documentmasterid = da.documentmasterid
		)`,
		stored.DocumentMasterID,
		compressedSize,
		stored.JobID,
		result.Status,
	)
	if err != nil {
		return databaseError(ctx, "updating compressed file size", err)
	}
	return nil
}

func updateDocumentMaster(
	ctx context.Context,
	tx *sql.Tx,
	stored storedJob,
	result CompressionResult,
) error {
	compressedPath := sql.NullString{String: result.CompressedPath, Valid: true}
	if result.Status == StatusSkipped && result.CompressedPath == "" {
		compressedPath = sql.NullString{Valid: false}
	}
	_, err := tx.ExecContext(ctx, `
		UPDATE "DocumentMaster" dm
		SET compressedfilepath = $2
		WHERE dm.documentmasterid = $1
		AND dm.ministryrequestid = $3
		AND EXISTS (
			SELECT 1
			FROM "CompressionJob" cj
			LEFT JOIN "DocumentDeleted" dd
				ON dd.ministryrequestid = $3
				AND dm.filepath ILIKE dd.filepath || '%'
			WHERE cj.compressionjobid = $5
			AND cj.version = 3
			AND cj.status = $4
			AND cj.documentmasterid = dm.documentmasterid
			AND (dd.filepath IS NULL OR dd.deleted IS FALSE OR dd.deleted IS NULL)
		)`,
		stored.DocumentMasterID,
		compressedPath,
		stored.MinistryRequestID,
		result.Status,
		stored.JobID,
	)
	if err != nil {
		return databaseError(ctx, "updating compressed file path", err)
	}
	return nil
}

type rowScanner interface {
	Scan(dest ...any) error
}

type queryRower interface {
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
}

type storedJob struct {
	Job
	DocumentMasterID  int
	MinistryRequestID int
}

func queryJob(ctx context.Context, queryer queryRower, query string, args ...any) (Job, error) {
	return scanJob(queryer.QueryRowContext(ctx, query, args...))
}

func queryStoredJob(
	ctx context.Context,
	queryer queryRower,
	query string,
	args ...any,
) (storedJob, error) {
	var stored storedJob
	var workload sql.NullString
	err := queryer.QueryRowContext(ctx, query, args...).Scan(
		&stored.JobID,
		&stored.Version,
		&stored.Status,
		&workload,
		&stored.CreatedAt,
		&stored.DocumentMasterID,
		&stored.MinistryRequestID,
	)
	if err != nil {
		return storedJob{}, err
	}
	if workload.Valid {
		stored.Workload = config.Workload(workload.String)
		stored.WorkloadKnown = true
	}
	return stored, nil
}

func scanJob(scanner rowScanner) (Job, error) {
	var job Job
	var workload sql.NullString
	if err := scanner.Scan(
		&job.JobID,
		&job.Version,
		&job.Status,
		&workload,
		&job.CreatedAt,
	); err != nil {
		return Job{}, err
	}
	if workload.Valid {
		job.Workload = config.Workload(workload.String)
		job.WorkloadKnown = true
	}
	return job, nil
}

func (r *Repository) operationContext(ctx context.Context) (context.Context, context.CancelFunc) {
	if r.options.OperationTimeout > 0 {
		return context.WithTimeout(ctx, r.options.OperationTimeout)
	}
	return context.WithCancel(ctx)
}

func (r *Repository) cleanupContext(ctx context.Context) (context.Context, context.CancelFunc) {
	return r.operationContext(context.WithoutCancel(ctx))
}

func databaseError(ctx context.Context, operation string, err error) error {
	if err == nil {
		return nil
	}
	if contextErr := ctx.Err(); contextErr != nil {
		return fmt.Errorf("%s: %w", operation, contextErr)
	}
	return fmt.Errorf("%s: %w", operation, err)
}

type credentialError struct {
	cause   error
	invalid bool
}

func (e credentialError) Error() string {
	if e.invalid {
		return ErrCredentialsInvalid.Error()
	}
	return "credentials_unavailable"
}

func (e credentialError) Unwrap() error {
	return e.cause
}

func (e credentialError) Is(target error) bool {
	return e.invalid && target == ErrCredentialsInvalid
}
