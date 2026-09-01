package main

import (
	"errors"
	"fmt"
	"log/slog"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestSafeCode(t *testing.T) {
	tests := []struct {
		err  error
		want string
	}{
		{fmt.Errorf("configuration_invalid: MESSAGING_STREAM_PREFIX must be foi"), "configuration_invalid"},
		{fmt.Errorf("database_unavailable: connection refused"), "database_unavailable"},
		{fmt.Errorf("consumer_initialization_failed: dial tcp"), "consumer_initialization_failed"},
		{errors.New("something unexpected"), "internal_error"},
	}
	for _, tc := range tests {
		got := safeCode(tc.err)
		require.Equal(t, tc.want, got, "safeCode(%q)", tc.err.Error())
	}
}

func TestLogLevelFromEnv(t *testing.T) {
	tests := []struct {
		input string
		want  slog.Level
	}{
		{"DEBUG", slog.LevelDebug},
		{"debug", slog.LevelDebug},
		{"WARN", slog.LevelWarn},
		{"WARNING", slog.LevelWarn},
		{"warn", slog.LevelWarn},
		{"ERROR", slog.LevelError},
		{"error", slog.LevelError},
		{"INFO", slog.LevelInfo},
		{"", slog.LevelInfo},
		{"UNKNOWN", slog.LevelInfo},
		{"  DEBUG  ", slog.LevelDebug},
	}
	for _, tc := range tests {
		got := logLevelFromEnv(tc.input)
		require.Equal(t, tc.want, got, "logLevelFromEnv(%q)", tc.input)
	}
}
