package compressor

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"os/exec"
	"strings"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"
)

const maxGhostscriptStderrBytes = 8 * 1024

// ExecRunner invokes commands directly without a shell.
type ExecRunner struct{}

// Run executes name with separate arguments and propagates ctx to the process.
func (ExecRunner) Run(
	ctx context.Context,
	name string,
	args []string,
	environment []string,
	stderr io.Writer,
) error {
	command := exec.CommandContext(ctx, name, args...)
	command.Env = append([]string{}, environment...)
	command.Stderr = stderr
	return command.Run()
}

func runGhostscript(
	ctx context.Context,
	runner CommandRunner,
	inputPath string,
	outputPath string,
	workDir string,
) error {
	if err := ctx.Err(); err != nil {
		return compression.NewRetryableFailure(store.FailureCodeGhostscriptTimeout, err)
	}

	arguments := []string{
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
		"-sOutputFile=" + outputPath,
		inputPath,
	}
	stderr := newBoundedBuffer(maxGhostscriptStderrBytes)
	err := runner.Run(
		ctx,
		"gs",
		arguments,
		tempEnvironment(workDir),
		stderr,
	)
	if err == nil {
		if contextErr := ctx.Err(); contextErr != nil {
			return compression.NewRetryableFailure(
				store.FailureCodeGhostscriptTimeout,
				contextErr,
			)
		}
		return nil
	}
	if ctx.Err() != nil {
		return compression.NewRetryableFailure(
			store.FailureCodeGhostscriptTimeout,
			errors.Join(ctx.Err(), err),
		)
	}

	if stderr.indicatesUnsupportedDocument() {
		return unsupportedDocument(err)
	}
	return compression.NewRetryableFailure(store.FailureCodeGhostscriptTimeout, err)
}

func tempEnvironment(workDir string) []string {
	environment := os.Environ()
	filtered := make([]string, 0, len(environment)+1)
	for _, variable := range environment {
		if strings.HasPrefix(variable, "TMPDIR=") {
			continue
		}
		filtered = append(filtered, variable)
	}
	return append(filtered, "TMPDIR="+workDir)
}

type boundedBuffer struct {
	buffer bytes.Buffer
	limit  int
}

func newBoundedBuffer(limit int) *boundedBuffer {
	return &boundedBuffer{limit: limit}
}

func (b *boundedBuffer) Write(p []byte) (int, error) {
	written := len(p)
	remaining := b.limit - b.buffer.Len()
	if remaining <= 0 {
		return written, nil
	}
	if len(p) > remaining {
		p = p[:remaining]
	}
	_, _ = b.buffer.Write(p)
	return written, nil
}

func (b *boundedBuffer) Len() int {
	return b.buffer.Len()
}

func (b *boundedBuffer) indicatesUnsupportedDocument() bool {
	diagnostic := bytes.ToLower(b.buffer.Bytes())
	return bytes.Contains(diagnostic, []byte("error: /syntaxerror in --runpdf--"))
}
