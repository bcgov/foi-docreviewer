package app

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"
)

func TestRunRejectsUnknownCommandBeforeLoadingConfiguration(t *testing.T) {
	t.Parallel()

	err := Run(context.Background(), []string{"unexpected"}, func(string) string {
		t.Fatal("configuration must not be loaded for an unknown command")
		return ""
	}, slog.New(slog.NewTextHandler(io.Discard, nil)))

	if err == nil {
		t.Fatal("Run() error = nil, want unknown command error")
	}
	if code := SafeCode(err); code != "unknown_command" {
		t.Fatalf("SafeCode() = %q, want unknown_command", code)
	}
}

func TestSafeCodeNeverExposesOperationalErrorText(t *testing.T) {
	t.Parallel()

	secret := "https://storage.example/document.pdf?X-Amz-Signature=token"
	code := SafeCode(errors.New("Ghostscript failed for " + secret))
	if code == "" || strings.Contains(code, secret) || strings.Contains(code, "Ghostscript") {
		t.Fatalf("SafeCode() = %q, must be a safe category", code)
	}
}
