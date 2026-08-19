package compressor

import (
	"context"
	"crypto/sha256"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestDownloadPropagatesRequestCancellation(t *testing.T) {
	t.Parallel()

	started := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		close(started)
		<-r.Context().Done()
	}))
	t.Cleanup(server.Close)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	t.Cleanup(cancel)
	go func() {
		<-started
		cancel()
	}()

	err := download(ctx, server.Client(), server.URL+"?credential=secret", io.Discard)

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.Equal(t, string(store.FailureCodeS3DownloadTimeout), err.Error())
	assert.NotContains(t, err.Error(), server.URL)
	assert.NotContains(t, err.Error(), "secret")
}

func TestUploadPropagatesRequestCancellation(t *testing.T) {
	t.Parallel()

	started := make(chan struct{})
	server := httptest.NewServer(http.HandlerFunc(func(_ http.ResponseWriter, r *http.Request) {
		_, _ = io.Copy(io.Discard, r.Body)
		close(started)
		<-r.Context().Done()
	}))
	t.Cleanup(server.Close)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	t.Cleanup(cancel)
	go func() {
		<-started
		cancel()
	}()

	err := upload(
		ctx,
		server.Client(),
		server.URL+"?credential=secret",
		strings.NewReader("payload"),
		int64(len("payload")),
	)

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.Equal(t, string(store.FailureCodeS3UploadFailed), err.Error())
	assert.NotContains(t, err.Error(), server.URL)
	assert.NotContains(t, err.Error(), "secret")
}

func TestDownloadRejectsNon2xxWithoutReadingOrReturningUnboundedBody(t *testing.T) {
	t.Parallel()

	responseBody := &trackingReadCloser{
		reader: strings.NewReader(strings.Repeat("sensitive-response-body", 1_000)),
	}
	client := &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusBadGateway,
			Body:       responseBody,
			Header:     make(http.Header),
		}, nil
	})}

	err := download(
		context.Background(),
		client,
		"https://presigned.example.invalid/private?token=secret",
		io.Discard,
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeS3DownloadTimeout), err.Error())
	assert.LessOrEqual(t, responseBody.bytesRead, int64(maxErrorBodyBytes))
	assert.True(t, responseBody.closed)
	assert.NotContains(t, err.Error(), "sensitive-response-body")
	assert.NotContains(t, err.Error(), "presigned.example.invalid")
	assert.NotContains(t, err.Error(), "secret")
}

func TestUploadStreamsExactBytesIncrementallyFromReader(t *testing.T) {
	t.Parallel()

	const payloadSize = 3*1024*1024 + 17
	received := make(chan uploadDigest, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hash := sha256.New()
		n, err := io.Copy(hash, r.Body)
		received <- uploadDigest{
			bytes:            n,
			hash:             hash.Sum(nil),
			contentLength:    r.ContentLength,
			transferEncoding: append([]string{}, r.TransferEncoding...),
			err:              err,
		}
		w.WriteHeader(http.StatusNoContent)
	}))
	t.Cleanup(server.Close)

	reader := &incrementalPatternReader{remaining: payloadSize, maxChunk: 4093}
	err := upload(context.Background(), server.Client(), server.URL, reader, payloadSize)

	require.NoError(t, err)
	got := <-received
	require.NoError(t, got.err)
	assert.EqualValues(t, payloadSize, got.bytes)
	assert.EqualValues(t, payloadSize, got.contentLength)
	assert.Empty(t, got.transferEncoding)
	assert.Greater(t, reader.calls, 1)
	assert.LessOrEqual(t, reader.largestRead, reader.maxChunk)

	expectedHash := sha256.New()
	_, err = io.Copy(expectedHash, &incrementalPatternReader{
		remaining: payloadSize,
		maxChunk:  4093,
	})
	require.NoError(t, err)
	assert.Equal(t, expectedHash.Sum(nil), got.hash)
}

func TestUploadStopsReadingWhenContextIsCanceled(t *testing.T) {
	t.Parallel()

	ctx, cancel := context.WithCancel(context.Background())
	reader := &cancelingReader{
		cancel: cancel,
		reader: &incrementalPatternReader{remaining: 8 * 1024 * 1024, maxChunk: 4096},
	}
	client := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		assert.EqualValues(t, 8*1024*1024, request.ContentLength)
		assert.Empty(t, request.TransferEncoding)
		buffer := make([]byte, 32*1024)
		for {
			if err := request.Context().Err(); err != nil {
				return nil, err
			}
			if _, err := request.Body.Read(buffer); err != nil {
				return nil, err
			}
		}
	})}

	err := upload(ctx, client, "https://upload.example.invalid", reader, 8*1024*1024)

	require.Error(t, err)
	assert.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, string(store.FailureCodeS3UploadFailed), err.Error())
	assert.Positive(t, reader.reads)
	assert.Less(t, reader.reads, (8*1024*1024)/4096)
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return f(request)
}

type trackingReadCloser struct {
	reader    io.Reader
	bytesRead int64
	closed    bool
}

func (r *trackingReadCloser) Read(p []byte) (int, error) {
	n, err := r.reader.Read(p)
	r.bytesRead += int64(n)
	return n, err
}

func (r *trackingReadCloser) Close() error {
	r.closed = true
	return nil
}

type incrementalPatternReader struct {
	mu          sync.Mutex
	remaining   int
	offset      int
	maxChunk    int
	calls       int
	largestRead int
}

func (r *incrementalPatternReader) Read(p []byte) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	if r.remaining == 0 {
		return 0, io.EOF
	}
	n := min(len(p), r.maxChunk, r.remaining)
	for index := range n {
		p[index] = byte((r.offset + index) % 251)
	}
	r.remaining -= n
	r.offset += n
	r.calls++
	r.largestRead = max(r.largestRead, n)
	return n, nil
}

type cancelingReader struct {
	cancel context.CancelFunc
	reader io.Reader
	reads  int
}

func (r *cancelingReader) Read(p []byte) (int, error) {
	r.reads++
	n, err := r.reader.Read(p)
	if r.reads == 1 {
		r.cancel()
	}
	return n, err
}

type uploadDigest struct {
	bytes            int64
	hash             []byte
	contentLength    int64
	transferEncoding []string
	err              error
}

var _ http.RoundTripper = roundTripFunc(nil)
var _ io.ReadCloser = (*trackingReadCloser)(nil)
var _ io.Reader = (*incrementalPatternReader)(nil)
var _ io.Reader = (*cancelingReader)(nil)

func TestUploadReturnsSafeFailureWhenTransportFails(t *testing.T) {
	t.Parallel()

	client := &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		return nil, errors.New("transport included token=secret")
	})}

	err := upload(
		context.Background(),
		client,
		"https://presigned.example.invalid/private?token=secret",
		strings.NewReader("payload"),
		int64(len("payload")),
	)

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeS3UploadFailed), err.Error())
	assert.NotContains(t, err.Error(), "token=secret")
}
