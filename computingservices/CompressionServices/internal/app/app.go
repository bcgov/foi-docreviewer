// Package app wires CompressionServices' long-lived dependencies and commands.
package app

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/compressor"
	"compressionservices/internal/config"
	"compressionservices/internal/consumer"
	"compressionservices/internal/followup"
	"compressionservices/internal/reconcile"
	"compressionservices/internal/store"

	"github.com/go-redis/redis/v8"
	_ "github.com/lib/pq"
)

const (
	commandConsume   = "consume"
	commandReconcile = "reconcile"

	startupTimeout      = 10 * time.Second
	databaseTimeout     = 30 * time.Second
	finalizationTimeout = 10 * time.Second
)

type safeError struct {
	code string
	err  error
}

func (e *safeError) Error() string { return e.code }
func (e *safeError) Unwrap() error { return e.err }

// SafeCode returns the bounded log-safe category for an application error.
func SafeCode(err error) string {
	var safe *safeError
	if errors.As(err, &safe) && safe.code != "" {
		return safe.code
	}
	return "internal_error"
}

func safe(code string, err error) error {
	return &safeError{code: code, err: err}
}

// Run selects and executes the requested command. With no command it consumes
// messages, preserving the historical container invocation contract.
func Run(ctx context.Context, args []string, getenv func(string) string, logger *slog.Logger) error {
	command, err := selectCommand(args)
	if err != nil {
		return err
	}
	if ctx == nil {
		return safe("invalid_context", context.Canceled)
	}
	if logger == nil {
		return safe("invalid_logger", errors.New("logger is required"))
	}
	if getenv == nil {
		return safe("configuration_invalid", errors.New("getenv is required"))
	}

	cfg, err := config.Load(getenv)
	if err != nil {
		return safe("configuration_invalid", err)
	}
	application, err := newApplication(ctx, command, cfg, logger)
	if err != nil {
		return err
	}

	var runErr error
	switch command {
	case commandConsume:
		runErr = application.consume(ctx)
	case commandReconcile:
		runErr = application.reconcile(ctx)
	}
	closeErr := application.close()
	if runErr != nil || closeErr != nil {
		return errors.Join(runErr, closeErr)
	}
	return nil
}

func selectCommand(args []string) (string, error) {
	if len(args) == 0 {
		return commandConsume, nil
	}
	if len(args) == 1 && (args[0] == commandConsume || args[0] == commandReconcile) {
		return args[0], nil
	}
	return "", safe("unknown_command", errors.New("unrecognized command"))
}

type runnable interface {
	Run(context.Context) error
	Close() error
}

type reconciliationRunner interface {
	RunOnce(context.Context) (reconcile.Summary, error)
}

type application struct {
	consumer    runnable
	reconciler  reconciliationRunner
	database    *sql.DB
	redisClient *redis.Client
}

func newApplication(ctx context.Context, command string, cfg config.Config, logger *slog.Logger) (*application, error) {
	database, err := openDatabase(ctx, cfg.Database)
	if err != nil {
		return nil, err
	}
	app := &application{database: database}
	if command == commandReconcile {
		app.reconciler = reconcile.New(store.New(database, store.Options{OperationTimeout: databaseTimeout}), reconcile.Options{
			Thresholds: store.Thresholds{
				Normal:  cfg.Reconciliation.NormalAfter,
				Large:   cfg.Reconciliation.LargeAfter,
				Unknown: cfg.Reconciliation.UnknownAfter,
			},
			BatchSize:           cfg.Reconciliation.BatchSize,
			FinalizationTimeout: finalizationTimeout,
		}, logger)
		return app, nil
	}

	redisClient := redis.NewClient(&redis.Options{Addr: cfg.Messaging.RedisAddress, Password: cfg.Messaging.RedisPassword})
	app.redisClient = redisClient
	repository := store.New(database, store.Options{OperationTimeout: databaseTimeout})
	signer, err := compressor.NewAWSSigner(cfg.S3.Endpoint, cfg.S3.Region, cfg.S3.PresignExpiry)
	if err != nil {
		_ = app.close()
		return nil, safe("configuration_invalid", err)
	}
	processor := compressor.New(compressor.Dependencies{
		CredentialStore:           repository,
		URLSigner:                 signer,
		HTTPClient:                newHTTPClient(),
		CommandRunner:             compressor.ExecRunner{},
		CompressionRatioThreshold: cfg.CompressionRatioThreshold,
		TempRoot:                  "",
	})
	followUp := followup.New(repository, redisClient, cfg.OCRStreamKey, logger)
	handler := compression.NewHandler(repository, processor, followUp, compression.Options{
		Workload:            cfg.Workload,
		ProcessingTimeout:   cfg.ProcessingTimeout,
		FinalizationTimeout: finalizationTimeout,
	})

	if cfg.Mode == config.ModeStandard {
		standard, standardErr := consumer.NewStandard(cfg, logger, handler)
		if standardErr != nil {
			_ = app.close()
			return nil, safe("consumer_initialization_failed", standardErr)
		}
		app.consumer = standard
		return app, nil
	}
	legacy := consumer.NewLegacy(redisLegacyStream{client: redisClient}, handler, consumer.LegacyOptions{
		StreamKey:     cfg.Messaging.LegacyStreamKey,
		CheckpointKey: cfg.Messaging.LegacyCheckpointKey,
		StartID:       "$",
		Workload:      cfg.Workload,
	})
	app.consumer = legacyRunner{legacy: legacy}
	return app, nil
}

func openDatabase(ctx context.Context, cfg config.Database) (*sql.DB, error) {
	dsn := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=disable", cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.Name)
	database, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, safe("database_unavailable", err)
	}
	database.SetMaxOpenConns(10)
	database.SetMaxIdleConns(5)
	database.SetConnMaxLifetime(30 * time.Minute)
	database.SetConnMaxIdleTime(5 * time.Minute)
	startupCtx, cancel := context.WithTimeout(ctx, startupTimeout)
	defer cancel()
	if err := database.PingContext(startupCtx); err != nil {
		_ = database.Close()
		return nil, safe("database_unavailable", err)
	}
	return database, nil
}

func newHTTPClient() *http.Client {
	return &http.Client{
		Transport: &http.Transport{
			DialContext:           (&net.Dialer{Timeout: 10 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
			TLSHandshakeTimeout:   10 * time.Second,
			ResponseHeaderTimeout: 30 * time.Second,
		},
	}
}

func (a *application) consume(ctx context.Context) error {
	if a == nil || a.consumer == nil {
		return safe("consumer_initialization_failed", errors.New("consumer is unavailable"))
	}
	if err := a.consumer.Run(ctx); err != nil {
		if errors.Is(err, context.Canceled) {
			return safe("consumer_stopped", err)
		}
		return safe("consumer_failed", err)
	}
	return nil
}

func (a *application) reconcile(ctx context.Context) error {
	if a == nil || a.reconciler == nil {
		return safe("reconciliation_unavailable", errors.New("reconciler is unavailable"))
	}
	if _, err := a.reconciler.RunOnce(ctx); err != nil {
		return safe("reconciliation_failed", err)
	}
	return nil
}

func (a *application) close() error {
	if a == nil {
		return nil
	}
	var result error
	if a.consumer != nil {
		if err := a.consumer.Close(); err != nil {
			result = errors.Join(result, safe("consumer_close_failed", err))
		}
	}
	if a.redisClient != nil {
		if err := a.redisClient.Close(); err != nil {
			result = errors.Join(result, safe("redis_close_failed", err))
		}
	}
	if a.database != nil {
		if err := a.database.Close(); err != nil {
			result = errors.Join(result, safe("database_close_failed", err))
		}
	}
	return result
}

type legacyRunner struct {
	legacy *consumer.Legacy
}

func (r legacyRunner) Run(ctx context.Context) error { return r.legacy.Run(ctx) }
func (r legacyRunner) Close() error                  { return nil }

type redisLegacyStream struct{ client *redis.Client }

func (s redisLegacyStream) LastID(ctx context.Context, key string) (string, error) {
	value, err := s.client.Get(ctx, key).Result()
	if errors.Is(err, redis.Nil) {
		return "", nil
	}
	return value, err
}

func (s redisLegacyStream) ReadAfter(ctx context.Context, stream, lastID string) ([]consumer.LegacyMessage, error) {
	streams, err := s.client.XRead(ctx, &redis.XReadArgs{Streams: []string{stream, lastID}, Block: 5 * time.Second}).Result()
	if errors.Is(err, redis.Nil) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	messages := make([]consumer.LegacyMessage, 0)
	for _, source := range streams {
		for _, message := range source.Messages {
			messages = append(messages, consumer.LegacyMessage{ID: message.ID, Values: message.Values})
		}
	}
	return messages, nil
}

func (s redisLegacyStream) SaveLastID(ctx context.Context, key, id string) error {
	return s.client.Set(ctx, key, id, 0).Err()
}
