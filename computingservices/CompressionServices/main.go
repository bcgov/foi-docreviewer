package main

import (
	"context"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"compressionservices/internal/app"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	if err := app.Run(ctx, os.Args[1:], os.Getenv, logger); err != nil {
		logStopped(logger, err)
		os.Exit(1)
	}
}

func logStopped(logger *slog.Logger, err error) {
	logger.Error("compression_service_stopped", "error_code", app.SafeCode(err))
}
