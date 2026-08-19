package compressor

import (
	"bytes"
	"context"
	"errors"
	"image"
	"image/color"
	"image/jpeg"
	"image/png"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"syscall"
	"testing"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestServiceCompressPDFStreamsDiskOutputAndReturnsCompleted(t *testing.T) {
	t.Parallel()

	input := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte("source-pdf-data"), 20_000)...)
	compressed := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte("compressed"), 100)...)
	uploaded := make(chan bodyCapture, 1)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			_, _ = w.Write(input)
		case http.MethodPut:
			body, err := io.ReadAll(r.Body)
			uploaded <- bodyCapture{
				body:             body,
				contentLength:    r.ContentLength,
				transferEncoding: append([]string{}, r.TransferEncoding...),
				err:              err,
			}
			w.WriteHeader(http.StatusCreated)
		default:
			w.WriteHeader(http.StatusMethodNotAllowed)
		}
	}))
	t.Cleanup(server.Close)

	tempRoot := t.TempDir()
	credentials := &fakeCredentialStore{
		credentials: models.S3Credentials{S3AccessKey: "access", S3SecretKey: "secret"},
		bucket:      "citz-test-e",
	}
	signer := &fakeURLSigner{
		downloadURL: server.URL + "/download?token=private",
		uploadURL:   server.URL + "/upload?token=private",
		objectPath:  "https://objects.example/citz-test-e/folder/inputCOMPRESSED.pdf",
	}
	runner := &fileCommandRunner{output: compressed}
	service := New(Dependencies{
		CredentialStore:           credentials,
		URLSigner:                 signer,
		HTTPClient:                server.Client(),
		CommandRunner:             runner,
		CompressionRatioThreshold: 0.9,
		TempRoot:                  tempRoot,
	})
	message := models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.pdf",
	}

	result, err := service.Compress(context.Background(), message)

	require.NoError(t, err)
	assert.Equal(t, store.StatusCompleted, result.Status)
	assert.Equal(t, signer.objectPath, result.CompressedPath)
	assert.EqualValues(t, len(compressed), result.CompressedSize)
	assert.Equal(t, ".pdf", result.Extension)
	upload := <-uploaded
	require.NoError(t, upload.err)
	assert.Equal(t, compressed, upload.body)
	assert.EqualValues(t, len(compressed), upload.contentLength)
	assert.Empty(t, upload.transferEncoding)
	assert.Equal(t, message.S3FilePath, signer.downloadPath)
	assert.Equal(t, message.S3FilePath, signer.uploadPath)
	assert.Equal(t, "citz-test-e", signer.downloadBucket)
	assert.Equal(t, "citz-test-e", signer.uploadBucket)
	assert.Equal(t, 1, runner.calls)
	assert.NoFileExists(t, runner.inputPath)
	assert.NoFileExists(t, runner.outputPath)
	assertTempRootEmpty(t, tempRoot)
}

func TestServiceCompressSkipsJBIG2WithoutRunningOrUploading(t *testing.T) {
	t.Parallel()

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = io.WriteString(w, "%PDF-1.4\n/JBIG2Decode\n")
	}))
	t.Cleanup(server.Close)

	tempRoot := t.TempDir()
	signer := &fakeURLSigner{downloadURL: server.URL}
	runner := &fileCommandRunner{output: []byte("must not run")}
	service := newTestService(server.Client(), signer, runner, tempRoot, 0.9)

	result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.pdf",
	})

	require.NoError(t, err)
	assert.Equal(t, store.CompressionResult{Status: store.StatusSkipped, Extension: ".pdf"}, result)
	assert.Zero(t, runner.calls)
	assert.Zero(t, signer.uploadCalls)
	assertTempRootEmpty(t, tempRoot)
}

func TestServiceCompressSkipsWhenPDFRatioExceedsThreshold(t *testing.T) {
	t.Parallel()

	input := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte{'a'}, 1_000)...)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(input)
	}))
	t.Cleanup(server.Close)

	tempRoot := t.TempDir()
	signer := &fakeURLSigner{downloadURL: server.URL}
	runner := &fileCommandRunner{output: bytes.Repeat([]byte{'b'}, 950)}
	service := newTestService(server.Client(), signer, runner, tempRoot, 0.9)

	result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.pdf",
	})

	require.NoError(t, err)
	assert.Equal(t, store.CompressionResult{Status: store.StatusSkipped, Extension: ".pdf"}, result)
	assert.Zero(t, signer.uploadCalls)
	assertTempRootEmpty(t, tempRoot)
}

func TestServiceCompressStreamsResizedImagesToOutputFile(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		extension string
		format    string
		encode    func(io.Writer, image.Image) error
	}{
		{
			name:      "jpeg",
			extension: ".jpg",
			format:    "jpeg",
			encode: func(writer io.Writer, source image.Image) error {
				return jpeg.Encode(writer, source, nil)
			},
		},
		{
			name:      "jpeg long extension",
			extension: ".jpeg",
			format:    "jpeg",
			encode: func(writer io.Writer, source image.Image) error {
				return jpeg.Encode(writer, source, nil)
			},
		},
		{
			name:      "png",
			extension: ".png",
			format:    "png",
			encode:    png.Encode,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()

			source := patternedImage(1_600, 800)
			var encoded bytes.Buffer
			require.NoError(t, test.encode(&encoded, source))

			uploaded := make(chan bodyCapture, 1)
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method == http.MethodGet {
					_, _ = w.Write(encoded.Bytes())
					return
				}
				body, err := io.ReadAll(r.Body)
				uploaded <- bodyCapture{body: body, err: err}
				w.WriteHeader(http.StatusOK)
			}))
			t.Cleanup(server.Close)

			tempRoot := t.TempDir()
			signer := &fakeURLSigner{
				downloadURL: server.URL,
				uploadURL:   server.URL,
				objectPath:  "https://objects.example/output" + test.extension,
			}
			service := newTestService(
				server.Client(),
				signer,
				&fileCommandRunner{},
				tempRoot,
				1,
			)

			result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
				BCGovCode:  "CITZ",
				S3FilePath: "s3://citz-test-e/folder/input" + test.extension,
			})

			require.NoError(t, err)
			assert.Equal(t, store.StatusCompleted, result.Status)
			assert.Equal(t, test.extension, result.Extension)
			upload := <-uploaded
			require.NoError(t, upload.err)
			output := upload.body
			assert.EqualValues(t, len(output), result.CompressedSize)
			resized, format, err := image.Decode(bytes.NewReader(output))
			require.NoError(t, err)
			assert.Equal(t, test.format, format)
			assert.Equal(t, 800, resized.Bounds().Dx())
			assert.Equal(t, 400, resized.Bounds().Dy())
			assertTempRootEmpty(t, tempRoot)
		})
	}
}

func TestServiceCompressRejectsUnsupportedDocumentWithoutCredentialLookup(t *testing.T) {
	t.Parallel()

	credentials := &fakeCredentialStore{}
	service := New(Dependencies{
		CredentialStore:           credentials,
		URLSigner:                 &fakeURLSigner{},
		HTTPClient:                http.DefaultClient,
		CommandRunner:             &fileCommandRunner{},
		CompressionRatioThreshold: 0.9,
		TempRoot:                  t.TempDir(),
	})

	result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.docx",
	})

	assert.Empty(t, result)
	require.Error(t, err)
	assert.True(t, compression.IsDeterministic(err))
	assert.Equal(t, string(store.FailureCodeUnsupportedDocument), err.Error())
	assert.Zero(t, credentials.calls)
}

func TestServiceCompressReturnsSafeCredentialFailure(t *testing.T) {
	t.Parallel()

	credentials := &fakeCredentialStore{err: errors.New("database exposed credential=secret")}
	service := New(Dependencies{
		CredentialStore:           credentials,
		URLSigner:                 &fakeURLSigner{},
		HTTPClient:                http.DefaultClient,
		CommandRunner:             &fileCommandRunner{},
		CompressionRatioThreshold: 0.9,
		TempRoot:                  t.TempDir(),
	})

	_, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.pdf",
	})

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
	assert.NotContains(t, err.Error(), "credential=secret")
}

func TestServiceCompressCleansTemporaryFilesAfterUploadFailure(t *testing.T) {
	t.Parallel()

	input := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte{'a'}, 10_000)...)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			_, _ = w.Write(input)
			return
		}
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = io.WriteString(w, "private object content and token=secret")
	}))
	t.Cleanup(server.Close)

	tempRoot := t.TempDir()
	signer := &fakeURLSigner{
		downloadURL: server.URL + "/download?token=secret",
		uploadURL:   server.URL + "/upload?token=secret",
		objectPath:  "https://objects.example/private.pdf",
	}
	runner := &fileCommandRunner{output: []byte("small compressed PDF")}
	service := newTestService(server.Client(), signer, runner, tempRoot, 0.9)

	_, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/folder/input.pdf",
	})

	require.Error(t, err)
	assert.Equal(t, string(store.FailureCodeS3UploadFailed), err.Error())
	assert.NotContains(t, err.Error(), "token=secret")
	assert.NotContains(t, err.Error(), "private object content")
	assertTempRootEmpty(t, tempRoot)
}

func TestServiceCompressRejectsImageExtensionMagicMismatch(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		extension string
		format    string
	}{
		{name: "jpeg bytes under png key", extension: ".png", format: "jpeg"},
		{name: "png bytes under jpg key", extension: ".jpg", format: "png"},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()

			input := encodedImageFixture(t, test.format)
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method == http.MethodGet {
					_, _ = w.Write(input)
					return
				}
				_, _ = io.Copy(io.Discard, r.Body)
				w.WriteHeader(http.StatusCreated)
			}))
			t.Cleanup(server.Close)

			signer := &fakeURLSigner{
				downloadURL: server.URL,
				uploadURL:   server.URL,
				objectPath:  "https://objects.example/output" + test.extension,
			}
			service := newTestService(
				server.Client(),
				signer,
				&fileCommandRunner{},
				t.TempDir(),
				1,
			)

			result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
				BCGovCode:  "CITZ",
				S3FilePath: "s3://citz-test-e/folder/input" + test.extension,
			})

			assert.Empty(t, result)
			require.Error(t, err)
			assert.True(t, compression.IsDeterministic(err))
			assert.Equal(t, string(store.FailureCodeUnsupportedDocument), err.Error())
			assert.Zero(t, signer.uploadCalls)
		})
	}
}

func TestServiceCompressMapsInvalidS3ObjectToDeterministicInvalidMessage(t *testing.T) {
	t.Parallel()

	transportCalled := false
	client := &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		transportCalled = true
		return nil, errors.New("unexpected transport call")
	})}
	signer := &fakeURLSigner{
		downloadErr: errors.Join(
			errInvalidS3Object,
			errors.New("private malformed object path"),
		),
	}
	service := newTestService(client, signer, &fileCommandRunner{}, t.TempDir(), 0.9)

	result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://wrong-bucket/input.pdf",
	})

	assert.Empty(t, result)
	require.Error(t, err)
	assert.True(t, compression.IsDeterministic(err))
	assert.ErrorIs(t, err, errInvalidS3Object)
	assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
	assert.NotContains(t, err.Error(), "private malformed object path")
	assert.False(t, transportCalled)
}

func TestServiceCompressKeepsOtherSigningFailuresRetryable(t *testing.T) {
	t.Parallel()

	signer := &fakeURLSigner{downloadErr: errors.New("signer unavailable with credential=secret")}
	service := newTestService(http.DefaultClient, signer, &fileCommandRunner{}, t.TempDir(), 0.9)

	_, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/input.pdf",
	})

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.Equal(t, string(store.FailureCodeS3DownloadTimeout), err.Error())
	assert.NotContains(t, err.Error(), "credential=secret")
}

func TestServiceCompressRejectsUnsafeRatioBeforeDependencies(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name  string
		ratio float64
	}{
		{name: "zero", ratio: 0},
		{name: "negative", ratio: -0.1},
		{name: "NaN", ratio: math.NaN()},
		{name: "positive infinity", ratio: math.Inf(1)},
		{name: "above one", ratio: 1.0001},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()

			credentials := &fakeCredentialStore{}
			service := New(Dependencies{
				CredentialStore:           credentials,
				URLSigner:                 &fakeURLSigner{},
				HTTPClient:                http.DefaultClient,
				CommandRunner:             &fileCommandRunner{},
				CompressionRatioThreshold: test.ratio,
				TempRoot:                  t.TempDir(),
			})

			_, err := service.Compress(context.Background(), models.CompressionProducerMessage{
				BCGovCode:  "CITZ",
				S3FilePath: "s3://citz-test-e/input.pdf",
			})

			require.Error(t, err)
			assert.True(t, compression.IsRetryable(err))
			assert.Equal(t, string(store.FailureCodeInvalidMessage), err.Error())
			assert.Zero(t, credentials.calls)
		})
	}
}

func TestServiceCompressHonorsCancellationBeforeJBIG2Skip(t *testing.T) {
	t.Parallel()

	ctx := newStepCancelContext(3)
	client := &http.Client{Transport: roundTripFunc(func(*http.Request) (*http.Response, error) {
		return &http.Response{
			StatusCode: http.StatusOK,
			Body:       io.NopCloser(strings.NewReader("%PDF-1.4\n/JBIG2Decode\n")),
			Header:     make(http.Header),
		}, nil
	})}
	signer := &fakeURLSigner{downloadURL: "https://download.example.invalid/input.pdf"}
	service := newTestService(client, signer, &fileCommandRunner{}, t.TempDir(), 0.9)

	result, err := service.Compress(ctx, models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/input.pdf",
	})

	assert.Empty(t, result)
	require.Error(t, err)
	assert.ErrorIs(t, err, context.Canceled)
	assert.Zero(t, signer.uploadCalls)
}

func TestServiceCompressHonorsCancellationBeforeRatioSkip(t *testing.T) {
	t.Parallel()

	input := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte{'a'}, 1_000)...)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(input)
	}))
	t.Cleanup(server.Close)

	ctx, cancel := context.WithCancel(context.Background())
	signer := &fakeURLSigner{downloadURL: server.URL}
	runner := &fileCommandRunner{
		output: bytes.Repeat([]byte{'b'}, 950),
		cancel: cancel,
	}
	service := newTestService(server.Client(), signer, runner, t.TempDir(), 0.9)

	result, err := service.Compress(ctx, models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/input.pdf",
	})

	assert.Empty(t, result)
	require.Error(t, err)
	assert.ErrorIs(t, err, context.Canceled)
	assert.Zero(t, signer.uploadCalls)
}

func TestServiceCompressSkipsOversizedSparseOutputBeforeSigning(t *testing.T) {
	t.Parallel()

	input := append([]byte("%PDF-1.4\n"), bytes.Repeat([]byte{'a'}, 1_000)...)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(input)
	}))
	t.Cleanup(server.Close)

	signer := &fakeURLSigner{downloadURL: server.URL}
	runner := &fileCommandRunner{
		output:     []byte("sparse"),
		outputSize: math.MaxInt32 + 1,
	}
	service := newTestService(server.Client(), signer, runner, t.TempDir(), 1)

	result, err := service.Compress(context.Background(), models.CompressionProducerMessage{
		BCGovCode:  "CITZ",
		S3FilePath: "s3://citz-test-e/input.pdf",
	})

	require.NoError(t, err)
	assert.Equal(t, store.CompressionResult{Status: store.StatusSkipped, Extension: ".pdf"}, result)
	assert.Zero(t, signer.uploadCalls)
}

func TestAWSSignerUsesFifteenMinuteSecurityMaximum(t *testing.T) {
	t.Parallel()

	signer, err := NewAWSSigner(
		"https://objects.example.test",
		"ca-central-1",
		15*time.Minute,
	)
	require.NoError(t, err)
	credentials := models.S3Credentials{
		S3AccessKey: "access-key",
		S3SecretKey: "secret-key",
	}

	downloadURL, err := signer.DownloadURL(
		context.Background(),
		credentials,
		"citz-test-e",
		"s3://citz-test-e/folder/input.pdf",
	)
	require.NoError(t, err)
	download, err := url.Parse(downloadURL)
	require.NoError(t, err)
	assert.Equal(t, "900", download.Query().Get("X-Amz-Expires"))
	assert.Equal(t, "/citz-test-e/folder/input.pdf", download.Path)

	uploadURL, objectPath, err := signer.UploadURL(
		context.Background(),
		credentials,
		"citz-test-e",
		"s3://citz-test-e/folder/input.pdf",
	)
	require.NoError(t, err)
	upload, err := url.Parse(uploadURL)
	require.NoError(t, err)
	assert.Equal(t, "900", upload.Query().Get("X-Amz-Expires"))
	assert.Equal(t, "/citz-test-e/folder/inputCOMPRESSED.pdf", upload.Path)
	assert.Equal(
		t,
		"https://objects.example.test/citz-test-e/folder/inputCOMPRESSED.pdf",
		objectPath,
	)
	assert.NotContains(t, objectPath, "access-key")
	assert.NotContains(t, objectPath, "secret-key")
}

func TestCompressedOutputPersistenceBoundary(t *testing.T) {
	t.Parallel()

	assert.False(t, exceedsCompressedSizeLimit(math.MaxInt32))
	assert.True(t, exceedsCompressedSizeLimit(math.MaxInt32+1))
}

func TestEncodeImageKeepsDiskWriteFailureRetryable(t *testing.T) {
	t.Parallel()

	err := encodeImage(
		context.Background(),
		failingWriter{err: syscall.ENOSPC},
		"png",
		image.NewRGBA(image.Rect(0, 0, 10, 10)),
	)

	require.Error(t, err)
	assert.True(t, compression.IsRetryable(err))
	assert.ErrorIs(t, err, syscall.ENOSPC)
	assert.Equal(t, string(store.FailureCodeDatabaseUnavailable), err.Error())
}

func newTestService(
	client *http.Client,
	signer URLSigner,
	runner CommandRunner,
	tempRoot string,
	ratio float64,
) *Service {
	return New(Dependencies{
		CredentialStore: &fakeCredentialStore{
			credentials: models.S3Credentials{S3AccessKey: "access", S3SecretKey: "secret"},
			bucket:      "citz-test-e",
		},
		URLSigner:                 signer,
		HTTPClient:                client,
		CommandRunner:             runner,
		CompressionRatioThreshold: ratio,
		TempRoot:                  tempRoot,
	})
}

func assertTempRootEmpty(t *testing.T, root string) {
	t.Helper()
	entries, err := os.ReadDir(root)
	require.NoError(t, err)
	assert.Empty(t, entries)
}

func patternedImage(width, height int) *image.RGBA {
	source := image.NewRGBA(image.Rect(0, 0, width, height))
	state := uint32(1)
	for y := range height {
		for x := range width {
			state = state*1_664_525 + 1_013_904_223
			red := uint8(state >> 24)
			state = state*1_664_525 + 1_013_904_223
			green := uint8(state >> 24)
			state = state*1_664_525 + 1_013_904_223
			blue := uint8(state >> 24)
			source.SetRGBA(x, y, color.RGBA{
				R: red,
				G: green,
				B: blue,
				A: 255,
			})
		}
	}
	return source
}

func encodedImageFixture(t *testing.T, format string) []byte {
	t.Helper()

	source := patternedImage(1_600, 800)
	var encoded bytes.Buffer
	var err error
	switch format {
	case "jpeg":
		err = jpeg.Encode(&encoded, source, nil)
	case "png":
		err = png.Encode(&encoded, source)
	default:
		t.Fatalf("unsupported test image format %q", format)
	}
	require.NoError(t, err)
	return encoded.Bytes()
}

type stepCancelContext struct {
	context.Context
	cancelAt int64
	calls    atomic.Int64
}

type failingWriter struct {
	err error
}

func (w failingWriter) Write([]byte) (int, error) {
	return 0, w.err
}

func newStepCancelContext(cancelAt int64) *stepCancelContext {
	return &stepCancelContext{
		Context:  context.Background(),
		cancelAt: cancelAt,
	}
}

func (c *stepCancelContext) Done() <-chan struct{} {
	return nil
}

func (c *stepCancelContext) Err() error {
	if c.calls.Add(1) >= c.cancelAt {
		return context.Canceled
	}
	return nil
}

type fakeCredentialStore struct {
	credentials models.S3Credentials
	bucket      string
	err         error
	calls       int
}

func (s *fakeCredentialStore) Credentials(
	context.Context,
	string,
) (models.S3Credentials, string, error) {
	s.calls++
	return s.credentials, s.bucket, s.err
}

type fakeURLSigner struct {
	mu             sync.Mutex
	downloadURL    string
	uploadURL      string
	objectPath     string
	downloadPath   string
	uploadPath     string
	downloadBucket string
	uploadBucket   string
	downloadErr    error
	uploadErr      error
	uploadCalls    int
}

func (s *fakeURLSigner) DownloadURL(
	_ context.Context,
	_ models.S3Credentials,
	bucket string,
	path string,
) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.downloadBucket = bucket
	s.downloadPath = path
	return s.downloadURL, s.downloadErr
}

func (s *fakeURLSigner) UploadURL(
	_ context.Context,
	_ models.S3Credentials,
	bucket string,
	path string,
) (string, string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.uploadCalls++
	s.uploadBucket = bucket
	s.uploadPath = path
	return s.uploadURL, s.objectPath, s.uploadErr
}

type fileCommandRunner struct {
	mu         sync.Mutex
	output     []byte
	err        error
	calls      int
	inputPath  string
	outputPath string
	outputSize int64
	cancel     context.CancelFunc
}

type bodyCapture struct {
	body             []byte
	contentLength    int64
	transferEncoding []string
	err              error
}

func (r *fileCommandRunner) Run(
	_ context.Context,
	_ string,
	args []string,
	_ []string,
	_ io.Writer,
) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.calls++
	r.inputPath = args[len(args)-1]
	for _, argument := range args {
		if outputPath, found := strings.CutPrefix(argument, "-sOutputFile="); found {
			r.outputPath = outputPath
			break
		}
	}
	if r.err != nil {
		return r.err
	}
	if err := os.WriteFile(r.outputPath, r.output, 0o600); err != nil {
		return err
	}
	if r.outputSize > 0 {
		if err := os.Truncate(r.outputPath, r.outputSize); err != nil {
			return err
		}
	}
	if r.cancel != nil {
		r.cancel()
	}
	return nil
}

var _ CredentialStore = (*fakeCredentialStore)(nil)
var _ URLSigner = (*fakeURLSigner)(nil)
var _ CommandRunner = (*fileCommandRunner)(nil)
var _ CommandRunner = ExecRunner{}
var _ io.Writer = failingWriter{}

func TestCompressedObjectKeyPreservesDirectoriesAndExtension(t *testing.T) {
	t.Parallel()

	key, err := compressedObjectKey("folder.with.dots/input.PDF")

	require.NoError(t, err)
	assert.Equal(t, filepath.ToSlash("folder.with.dots/inputCOMPRESSED.PDF"), key)
}
