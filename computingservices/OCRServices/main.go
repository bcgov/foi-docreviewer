package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"ocrservices/internal/app"
)

func main() {
	level := logLevelFromEnv(os.Getenv("LOG_LEVEL"))
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := app.Run(ctx, os.Getenv, logger); err != nil {
		logger.Error("ocr_service_stopped", "error_code", safeCode(err))
		os.Exit(1)
	}
}

func logLevelFromEnv(value string) slog.Level {
	switch strings.ToUpper(strings.TrimSpace(value)) {
	case "DEBUG":
		return slog.LevelDebug
	case "WARN", "WARNING":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

// safeCode returns a bounded, log-safe category for a startup/run error.
func safeCode(err error) string {
	msg := err.Error()
	switch {
	case strings.Contains(msg, "configuration_invalid"):
		return "configuration_invalid"
	case strings.Contains(msg, "database_unavailable"):
		return "database_unavailable"
	case strings.Contains(msg, "consumer_initialization_failed"):
		return "consumer_initialization_failed"
	default:
		return "internal_error"
	}
}
