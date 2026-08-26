package main

import (
	"bytes"
	"errors"
	"log/slog"
	"strings"
	"testing"
)

func TestLogStoppedUsesOnlySafeErrorCode(t *testing.T) {
	t.Parallel()

	var output bytes.Buffer
	logger := slog.New(slog.NewJSONHandler(&output, nil))
	secret := "https://s3.example/files/private.pdf?token=do-not-log"
	logStopped(logger, errors.New("Ghostscript failed for report.pdf: "+secret))

	logs := output.String()
	for _, forbidden := range []string{secret, "report.pdf", "Ghostscript"} {
		if strings.Contains(logs, forbidden) {
			t.Fatalf("log output exposes %q: %s", forbidden, logs)
		}
	}
	if !strings.Contains(logs, `"error_code":"internal_error"`) {
		t.Fatalf("log output = %s, want internal_error code", logs)
	}
}
