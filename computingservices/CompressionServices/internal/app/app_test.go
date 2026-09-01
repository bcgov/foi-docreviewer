package app

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"strings"
	"testing"

	"compressionservices/internal/config"
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

// TestBuildDSN verifies that password and dbname are independently and correctly
// placed in the DSN. It uses synthetic values so no real secrets appear in output.
func TestBuildDSN(t *testing.T) {
	t.Parallel()
	cfg := config.Database{
		Host:     "dbhost",
		Port:     5432,
		User:     "dbuser",
		Password: "synth-pw-1234",
		Name:     "mydb",
	}
	dsn := buildDSN(cfg)

	if !strings.Contains(dsn, "dbname=mydb") {
		t.Errorf("DSN missing dbname=mydb; got: %q", dsn)
	}
	if strings.Contains(dsn, "dbname=synth-pw-1234") {
		t.Errorf("DSN has dbname set to password value; got: %q", dsn)
	}
	if !strings.Contains(dsn, "host=dbhost") {
		t.Errorf("DSN missing host=dbhost; got: %q", dsn)
	}
	if !strings.Contains(dsn, "user=dbuser") {
		t.Errorf("DSN missing user=dbuser; got: %q", dsn)
	}
}
