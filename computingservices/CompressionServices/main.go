package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"strings"
	"syscall"

	"compressionservices/internal/app"
)

func main() {
	level := logLevelFromEnv(os.Getenv("LOG_LEVEL"))
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: level}))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := app.Run(ctx, os.Args[1:], os.Getenv, logger); err != nil {
		logStopped(logger, err)
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

func logStopped(logger *slog.Logger, err error) {
	logger.Error("compression_service_stopped", "error_code", app.SafeCode(err))
}
