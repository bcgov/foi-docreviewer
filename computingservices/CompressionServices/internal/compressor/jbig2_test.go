package compressor

import (
	"bytes"
	"context"
	"errors"
	"io"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestScanJBIG2FindsMarkerAcrossChunkBoundary(t *testing.T) {
	t.Parallel()

	prefix := bytes.Repeat([]byte{'a'}, scanChunkSize-5)
	input := append(prefix, []byte("/JBIG2Decode")...)

	found, err := scanJBIG2(context.Background(), bytes.NewReader(input))

	require.NoError(t, err)
	assert.True(t, found)
}

func TestScanJBIG2ChecksCancellationBeforeEveryRead(t *testing.T) {
	t.Parallel()

	ctx, cancel := context.WithCancel(context.Background())
	input := append(
		bytes.Repeat([]byte{'a'}, scanChunkSize-len(jbig2Marker)),
		jbig2Marker...,
	)
	reader := &cancelAfterFirstRead{
		cancel: cancel,
		data:   input,
	}

	found, err := scanJBIG2(ctx, reader)

	assert.False(t, found)
	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, 1, reader.reads)
}

func TestScanJBIG2ReturnsReaderFailure(t *testing.T) {
	t.Parallel()

	readerErr := errors.New("reader failed")
	found, err := scanJBIG2(context.Background(), failingReader{err: readerErr})

	assert.False(t, found)
	require.ErrorIs(t, err, readerErr)
}

type cancelAfterFirstRead struct {
	cancel context.CancelFunc
	data   []byte
	reads  int
}

func (r *cancelAfterFirstRead) Read(p []byte) (int, error) {
	r.reads++
	if r.reads > 1 {
		return 0, errors.New("scan read after cancellation")
	}
	n := copy(p, r.data)
	r.cancel()
	return n, nil
}

type failingReader struct {
	err error
}

func (r failingReader) Read([]byte) (int, error) {
	return 0, r.err
}

var _ io.Reader = (*cancelAfterFirstRead)(nil)
