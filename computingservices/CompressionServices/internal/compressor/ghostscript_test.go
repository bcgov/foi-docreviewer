package compressor

import (
	"context"
	"errors"
	"io"
	"os/exec"
	"slices"
	"strings"
	"syscall"
	"testing"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRunGhostscriptReceivesCallerContextAndOutputPath(t *testing.T) {
	t.Parallel()

	type contextKey string
	ctx := context.WithValue(context.Background(), contextKey("request"), "request-41")
	runner := &recordingCommandRunner{}

	err := runGhostscript(ctx, runner, "/private/input.pdf", "/private/output.pdf", "/private/work")

	require.NoError(t, err)
	assert.Same(t, ctx, runner.ctx)
	assert.Equal(t, "gs", runner.name)
	assert.Equal(t, []string{
		"-sDEVICE=pdfwrite",
		"-dCompatibilityLevel=1.4",
		"-dPDFSETTINGS=/ebook",
		"-dNOPAUSE",
		"-dQUIET",
		"-dBATCH",
		"-dOptimize=true",
		"-dSubsetFonts=true",
		"-dDownsampleColorImages=true",
		"-dDownsampleGrayImages=true",
		"-dColorImageResolution=150",
		"-dGrayImageResolution=150",
		"-dRemoveAllUnusedObjects=true",
		"-dDetectDuplicateImages=true",
		"-sOutputFile=/private/output.pdf",
		"/private/input.pdf",
	}, runner.args)
	assert.True(t, slices.Contains(runner.env, "TMPDIR=/private/work"))
}

func TestRunGhostscriptBoundsAndRedactsStderr(t *testing.T) {
	t.Parallel()

	runnerErr := errors.New("ghostscript process failed")
	runner := &recordingCommandRunner{
		stderr: strings.Repeat("private-document-content", 1_000),
		err:    runnerErr,
	}

	err := runGhostscript(
		context.Background(),
		runner,
		"/private/input.pdf",
		"/private/output.pdf",
		"/private/work",
	)

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.ErrorIs(t, err, runnerErr)
	assert.Equal(t, string(store.FailureCodeGhostscriptTimeout), err.Error())
	assert.Equal(t, maxGhostscriptStderrBytes, runner.capturedStderrBytes)
	assert.NotContains(t, err.Error(), "private-document-content")
	assert.NotContains(t, err.Error(), "/private/input.pdf")
}

func TestRunGhostscriptClassifiesOnlyRecognizedCorruptInputDiagnosticAsUnsupported(t *testing.T) {
	t.Parallel()

	runnerErr := errors.New("exit status 1")
	runner := &recordingCommandRunner{
		stderr: "Error: /syntaxerror in --runpdf--\nprivate-document-content",
		err:    runnerErr,
	}

	err := runGhostscript(
		context.Background(),
		runner,
		"/private/input.pdf",
		"/private/output.pdf",
		"/private/work",
	)

	require.Error(t, err)
	assert.True(t, compression.IsDeterministic(err))
	assert.ErrorIs(t, err, runnerErr)
	assert.Equal(t, string(store.FailureCodeUnsupportedDocument), err.Error())
	assert.NotContains(t, err.Error(), "syntaxerror")
	assert.NotContains(t, err.Error(), "private-document-content")
}

func TestRunGhostscriptKeepsUnknownInfrastructureFailuresRetryable(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		err  error
	}{
		{name: "exit", err: errors.New("exit status 1")},
		{name: "signal", err: errors.New("signal: killed")},
		{name: "missing executable", err: &exec.Error{Name: "gs", Err: exec.ErrNotFound}},
		{name: "disk full", err: syscall.ENOSPC},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()

			runner := &recordingCommandRunner{
				stderr: "private-document-content",
				err:    test.err,
			}
			err := runGhostscript(
				context.Background(),
				runner,
				"/private/input.pdf",
				"/private/output.pdf",
				"/private/work",
			)

			require.Error(t, err)
			assert.True(t, compression.IsRetryable(err))
			assert.ErrorIs(t, err, test.err)
			assert.Equal(t, string(store.FailureCodeGhostscriptTimeout), err.Error())
			assert.NotContains(t, err.Error(), "private-document-content")
		})
	}
}

func TestRunGhostscriptReturnsSafeTimeoutForCanceledCommand(t *testing.T) {
	t.Parallel()

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	runner := &recordingCommandRunner{err: context.Canceled}

	err := runGhostscript(
		ctx,
		runner,
		"/private/input.pdf",
		"/private/output.pdf",
		"/private/work",
	)

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, string(store.FailureCodeGhostscriptTimeout), err.Error())
}

type recordingCommandRunner struct {
	ctx                 context.Context
	name                string
	args                []string
	env                 []string
	stderr              string
	err                 error
	capturedStderrBytes int
}

func (r *recordingCommandRunner) Run(
	ctx context.Context,
	name string,
	args []string,
	env []string,
	stderr io.Writer,
) error {
	r.ctx = ctx
	r.name = name
	r.args = append([]string{}, args...)
	r.env = append([]string{}, env...)
	if r.stderr != "" {
		_, _ = io.WriteString(stderr, r.stderr)
	}
	if sized, ok := stderr.(interface{ Len() int }); ok {
		r.capturedStderrBytes = sized.Len()
	}
	return r.err
}

var _ CommandRunner = (*recordingCommandRunner)(nil)
