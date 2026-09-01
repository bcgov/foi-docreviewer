package app

import (
	"context"
	"database/sql"
	"log/slog"
	"strings"
	"testing"

	"ocrservices/internal/config"

	"github.com/stretchr/testify/require"
)

func TestRunNilContext(t *testing.T) {
	//nolint:staticcheck // intentional nil context to exercise guard
	err := Run(nil, func(string) string { return "" }, slog.Default())
	require.EqualError(t, err, "context is required")
}

func TestRunNilGetenv(t *testing.T) {
	err := Run(context.Background(), nil, slog.Default())
	require.EqualError(t, err, "getenv is required")
}

func TestRunNilLogger(t *testing.T) {
	err := Run(context.Background(), func(string) string { return "" }, nil)
	require.EqualError(t, err, "logger is required")
}

func TestRunInvalidConfigWrapped(t *testing.T) {
	// getenv returns empty strings → config validation fails
	err := Run(context.Background(), func(string) string { return "" }, slog.Default())
	require.Error(t, err)
	require.True(t, strings.HasPrefix(err.Error(), "configuration_invalid:"),
		"expected configuration_invalid prefix, got: %s", err.Error())
}

// TestBuildDSN verifies that password and dbname are independently and correctly
// placed in the DSN. It uses synthetic values so no real secrets appear in output.
func TestBuildDSN(t *testing.T) {
	t.Parallel()
	cfg := config.Database{
		Host:     "dbhost",
		Port:     "5432",
		User:     "dbuser",
		Password: "synth-pw-1234",
		Name:     "mydb",
	}
	dsn := buildDSN(cfg)

	require.Contains(t, dsn, "dbname=mydb",
		"dbname must be set to the database name field")
	require.NotContains(t, dsn, "dbname=synth-pw-1234",
		"dbname must not be set to the password value")
	require.NotContains(t, dsn, "dbname=dbuser",
		"dbname must not be set to the user value")
	require.Contains(t, dsn, "host=dbhost")
	require.Contains(t, dsn, "port=5432")
	require.Contains(t, dsn, "user=dbuser")
}

// TestOpenDatabaseContextCancellationPropagatesClean verifies that a parent
// context cancellation during the startup ping is returned as context.Canceled
// (not wrapped in database_unavailable) so Run can exit cleanly.
func TestOpenDatabaseContextCancellationPropagatesClean(t *testing.T) {
	// NOTE: t.Parallel() is intentionally omitted — this test mutates the
	// package-level pingFn global and must not run concurrently with other
	// tests that read or write the same variable.

	// Replace the startup ping to simulate parent context cancellation.
	orig := pingFn
	defer func() { pingFn = orig }()
	pingFn = func(_ *sql.DB, _ context.Context) error {
		return context.Canceled
	}

	cfg := config.Database{Host: "localhost", Port: "5432", User: "u", Password: "p", Name: "db"}
	db, err := openDatabase(context.Background(), cfg)

	require.Nil(t, db, "db must be nil on ping failure")
	require.ErrorIs(t, err, context.Canceled,
		"error must unwrap to context.Canceled")
	require.NotContains(t, err.Error(), "database_unavailable",
		"context cancellation must not be wrapped as database_unavailable")
}
