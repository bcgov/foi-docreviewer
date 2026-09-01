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

	"ocrservices/internal/activemq"
	"ocrservices/internal/config"
	"ocrservices/internal/consumer"
	"ocrservices/internal/ocr"
	"ocrservices/internal/store"

	_ "github.com/lib/pq"
)

const startupTimeout = 10 * time.Second

// pingFn is the function used to verify the DB connection at startup.
// Replaced in tests to simulate cancellation without a live Postgres instance.
var pingFn = func(db *sql.DB, ctx context.Context) error {
	return db.PingContext(ctx)
}

// buildDSN constructs a lib/pq keyword=value DSN from database config.
// The DSN is never logged; callers must not pass it to any logger.
func buildDSN(cfg config.Database) string {
	return fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		cfg.Host, cfg.Port, cfg.User, cfg.Password, cfg.Name)
}

// Run loads config, wires dependencies, and consumes until ctx is cancelled.
func Run(ctx context.Context, getenv func(string) string, logger *slog.Logger) (retErr error) {
	if ctx == nil {
		return errors.New("context is required")
	}
	if getenv == nil {
		return errors.New("getenv is required")
	}
	if logger == nil {
		return errors.New("logger is required")
	}

	cfg, err := config.Load(getenv)
	if err != nil {
		return fmt.Errorf("configuration_invalid: %w", err)
	}

	db, err := openDatabase(ctx, cfg.Database)
	if err != nil {
		if errors.Is(err, context.Canceled) {
			return nil
		}
		return err
	}
	defer func() {
		if cerr := db.Close(); cerr != nil && retErr == nil {
			retErr = cerr
		}
	}()

	processor := ocr.NewProcessor(
		store.New(db),
		activemq.New(newHTTPClient(), cfg.ActiveMQ.URL, cfg.ActiveMQ.Username, cfg.ActiveMQ.Password, cfg.ActiveMQ.Destination),
		cfg.ProcessingTimeout,
		logger,
	)
	standard, err := consumer.NewStandard(cfg, logger, processor)
	if err != nil {
		return fmt.Errorf("consumer_initialization_failed: %w", err)
	}

	runErr := standard.Run(ctx)
	closeErr := standard.Close()
	if runErr != nil && !errors.Is(runErr, context.Canceled) {
		retErr = errors.Join(runErr, closeErr)
		return
	}
	retErr = closeErr
	return
}

func openDatabase(ctx context.Context, cfg config.Database) (*sql.DB, error) {
	db, err := sql.Open("postgres", buildDSN(cfg))
	if err != nil {
		return nil, fmt.Errorf("database_unavailable: %w", err)
	}
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	db.SetConnMaxLifetime(30 * time.Minute)
	db.SetConnMaxIdleTime(5 * time.Minute)
	pingCtx, cancel := context.WithTimeout(ctx, startupTimeout)
	defer cancel()
	if err := pingFn(db, pingCtx); err != nil {
		_ = db.Close()
		if errors.Is(err, context.Canceled) {
			return nil, context.Canceled
		}
		return nil, fmt.Errorf("database_unavailable: %w", err)
	}
	return db, nil
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
