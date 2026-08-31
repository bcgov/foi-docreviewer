package store

import (
	"context"
	"regexp"
	"testing"

	"ocrservices/models"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/stretchr/testify/require"
)

func TestTerminalExistsTrue(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	mock.ExpectQuery(regexp.QuoteMeta(sqlTerminalExists)).
		WithArgs(42, versionTerminal).WillReturnRows(sqlmock.NewRows([]string{"count"}).AddRow(1))
	got, err := New(db).TerminalExists(context.Background(), 42)
	require.NoError(t, err)
	require.True(t, got)
	require.NoError(t, mock.ExpectationsWereMet())
}

func TestEnsureStartedInserts(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()
	mock.ExpectExec(regexp.QuoteMeta(sqlEnsureStarted)).
		WithArgs(42, versionStarted, 7, "b1", "trig", "f.pdf", statusStarted, 9).
		WillReturnResult(sqlmock.NewResult(0, 1))
	m := models.OCRProducerMessage{JobID: 42, MinistryRequestID: 7, Batch: "b1", Trigger: "trig", Filename: "f.pdf", DocumentMasterID: 9}
	require.NoError(t, New(db).EnsureStarted(context.Background(), m))
	require.NoError(t, mock.ExpectationsWereMet())
}
