// Package compressor performs bounded, disk-streamed document compression.
package compressor

import (
	"context"
	"errors"
	"image"
	"image/jpeg"
	"image/png"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"reflect"
	"strings"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/nfnt/resize"
)

const resizedImageWidth uint = 800

var errInvalidDependencies = errors.New("invalid compressor dependencies")

// CredentialStore looks up the credentials and bucket for a ministry code.
type CredentialStore interface {
	Credentials(context.Context, string) (models.S3Credentials, string, error)
}

// URLSigner creates bounded-lifetime S3 transfer URLs without performing I/O.
type URLSigner interface {
	DownloadURL(
		context.Context,
		models.S3Credentials,
		string,
		string,
	) (string, error)
	UploadURL(
		context.Context,
		models.S3Credentials,
		string,
		string,
	) (string, string, error)
}

// CommandRunner executes an external compressor with caller-owned cancellation.
type CommandRunner interface {
	Run(context.Context, string, []string, []string, io.Writer) error
}

// Dependencies contains the shared and configurable resources used by Service.
type Dependencies struct {
	CredentialStore           CredentialStore
	URLSigner                 URLSigner
	HTTPClient                *http.Client
	CommandRunner             CommandRunner
	CompressionRatioThreshold float64
	TempRoot                  string
}

// Service compresses one document without buffering complete objects in memory.
type Service struct {
	credentials CredentialStore
	signer      URLSigner
	httpClient  *http.Client
	runner      CommandRunner
	ratio       float64
	tempRoot    string
}

// New constructs a compressor service from explicit dependencies.
func New(dependencies Dependencies) *Service {
	return &Service{
		credentials: dependencies.CredentialStore,
		signer:      dependencies.URLSigner,
		httpClient:  dependencies.HTTPClient,
		runner:      dependencies.CommandRunner,
		ratio:       dependencies.CompressionRatioThreshold,
		tempRoot:    dependencies.TempRoot,
	}
}

// Compress downloads, processes, and conditionally uploads one document.
func (s *Service) Compress(
	ctx context.Context,
	message models.CompressionProducerMessage,
) (store.CompressionResult, error) {
	if ctx == nil || !s.valid() {
		return store.CompressionResult{}, compression.NewRetryableFailure(
			store.FailureCodeInvalidMessage,
			errInvalidDependencies,
		)
	}

	extension, err := supportedExtension(message.S3FilePath)
	if err != nil {
		return store.CompressionResult{}, unsupportedDocument(err)
	}

	credentials, bucket, err := s.credentials.Credentials(ctx, message.BCGovCode)
	if err != nil {
		return store.CompressionResult{}, compression.NewRetryableFailure(
			store.FailureCodeDatabaseUnavailable,
			err,
		)
	}

	downloadURL, err := s.signer.DownloadURL(
		ctx,
		credentials,
		bucket,
		message.S3FilePath,
	)
	if err != nil {
		if errors.Is(err, errInvalidS3Object) {
			return store.CompressionResult{}, compression.NewDeterministicFailure(
				store.FailureCodeInvalidMessage,
				err,
			)
		}
		return store.CompressionResult{}, compression.NewRetryableFailure(
			store.FailureCodeS3DownloadTimeout,
			err,
		)
	}

	workDir, err := os.MkdirTemp(s.tempRoot, "compression-*")
	if err != nil {
		return store.CompressionResult{}, processingFailure(ctx, err)
	}
	defer func() {
		_ = os.RemoveAll(workDir)
	}()

	inputPath, err := s.downloadToFile(ctx, workDir, extension, downloadURL)
	if err != nil {
		return store.CompressionResult{}, err
	}

	inputInfo, err := os.Stat(inputPath)
	if err != nil {
		return store.CompressionResult{}, processingFailure(ctx, err)
	}
	if inputInfo.Size() == 0 {
		return store.CompressionResult{}, unsupportedDocument(errors.New("empty input document"))
	}

	outputPath, skipped, err := s.process(ctx, workDir, inputPath, extension)
	if err != nil {
		return store.CompressionResult{}, err
	}
	if skipped {
		if err := ctx.Err(); err != nil {
			return store.CompressionResult{}, processingFailure(ctx, err)
		}
		return skippedResult(extension), nil
	}

	outputInfo, err := os.Stat(outputPath)
	if err != nil {
		return store.CompressionResult{}, processingFailure(ctx, err)
	}
	if outputInfo.Size() == 0 {
		return store.CompressionResult{}, unsupportedDocument(errors.New("empty compressed document"))
	}
	if exceedsCompressedSizeLimit(outputInfo.Size()) {
		if err := ctx.Err(); err != nil {
			return store.CompressionResult{}, processingFailure(ctx, err)
		}
		return skippedResult(extension), nil
	}

	ratio := float64(outputInfo.Size()) / float64(inputInfo.Size())
	if ratio > s.ratio {
		if err := ctx.Err(); err != nil {
			return store.CompressionResult{}, processingFailure(ctx, err)
		}
		return skippedResult(extension), nil
	}

	uploadURL, objectPath, err := s.signer.UploadURL(
		ctx,
		credentials,
		bucket,
		message.S3FilePath,
	)
	if err != nil {
		if errors.Is(err, errInvalidS3Object) {
			return store.CompressionResult{}, compression.NewDeterministicFailure(
				store.FailureCodeInvalidMessage,
				err,
			)
		}
		return store.CompressionResult{}, compression.NewRetryableFailure(
			store.FailureCodeS3UploadFailed,
			err,
		)
	}

	outputFile, err := os.Open(outputPath)
	if err != nil {
		return store.CompressionResult{}, processingFailure(ctx, err)
	}
	uploadErr := upload(ctx, s.httpClient, uploadURL, outputFile, outputInfo.Size())
	closeErr := outputFile.Close()
	if uploadErr != nil {
		return store.CompressionResult{}, uploadErr
	}
	if closeErr != nil {
		return store.CompressionResult{}, processingFailure(ctx, closeErr)
	}

	return store.CompressionResult{
		Status:         store.StatusCompleted,
		CompressedPath: objectPath,
		CompressedSize: outputInfo.Size(),
		Extension:      extension,
	}, nil
}

func (s *Service) valid() bool {
	return s != nil &&
		!nilInterface(s.credentials) &&
		!nilInterface(s.signer) &&
		s.httpClient != nil &&
		!nilInterface(s.runner) &&
		!math.IsNaN(s.ratio) &&
		!math.IsInf(s.ratio, 0) &&
		s.ratio > 0 &&
		s.ratio <= 1
}

func (s *Service) downloadToFile(
	ctx context.Context,
	workDir string,
	extension string,
	downloadURL string,
) (string, error) {
	inputFile, err := os.CreateTemp(workDir, "input-*"+extension)
	if err != nil {
		return "", processingFailure(ctx, err)
	}

	downloadErr := download(ctx, s.httpClient, downloadURL, inputFile)
	closeErr := inputFile.Close()
	if downloadErr != nil {
		return "", downloadErr
	}
	if closeErr != nil {
		return "", processingFailure(ctx, closeErr)
	}
	return inputFile.Name(), nil
}

func (s *Service) process(
	ctx context.Context,
	workDir string,
	inputPath string,
	extension string,
) (string, bool, error) {
	switch extension {
	case ".pdf":
		return s.processPDF(ctx, workDir, inputPath)
	case ".jpg", ".jpeg", ".png":
		outputPath, err := processImage(ctx, workDir, inputPath, extension)
		return outputPath, false, err
	default:
		return "", false, unsupportedDocument(errors.New("unsupported document extension"))
	}
}

func (s *Service) processPDF(
	ctx context.Context,
	workDir string,
	inputPath string,
) (string, bool, error) {
	inputFile, err := os.Open(inputPath)
	if err != nil {
		return "", false, processingFailure(ctx, err)
	}
	hasJBIG2, scanErr := scanJBIG2(ctx, inputFile)
	closeErr := inputFile.Close()
	if scanErr != nil {
		return "", false, processingFailure(ctx, scanErr)
	}
	if closeErr != nil {
		return "", false, processingFailure(ctx, closeErr)
	}
	if hasJBIG2 {
		if err := ctx.Err(); err != nil {
			return "", false, processingFailure(ctx, err)
		}
		return "", true, nil
	}

	outputFile, err := os.CreateTemp(workDir, "output-*.pdf")
	if err != nil {
		return "", false, processingFailure(ctx, err)
	}
	outputPath := outputFile.Name()
	if err := outputFile.Close(); err != nil {
		return "", false, processingFailure(ctx, err)
	}
	if err := runGhostscript(ctx, s.runner, inputPath, outputPath, workDir); err != nil {
		return "", false, err
	}
	return outputPath, false, nil
}

func processImage(
	ctx context.Context,
	workDir string,
	inputPath string,
	extension string,
) (outputPath string, err error) {
	if err := ctx.Err(); err != nil {
		return "", processingFailure(ctx, err)
	}

	inputFile, err := os.Open(inputPath)
	if err != nil {
		return "", processingFailure(ctx, err)
	}
	defer func() {
		if closeErr := inputFile.Close(); closeErr != nil && err == nil {
			err = processingFailure(ctx, closeErr)
			outputPath = ""
		}
	}()

	decoded, format, err := image.Decode(contextReader{ctx: ctx, reader: inputFile})
	if err != nil {
		if ctx.Err() != nil {
			return "", processingFailure(ctx, errors.Join(err, ctx.Err()))
		}
		return "", unsupportedDocument(err)
	}
	if err := ctx.Err(); err != nil {
		return "", processingFailure(ctx, err)
	}
	if !imageFormatMatchesExtension(format, extension) {
		return "", unsupportedDocument(errors.New("image format does not match extension"))
	}

	resized := resize.Resize(resizedImageWidth, 0, decoded, resize.Lanczos3)
	if err := ctx.Err(); err != nil {
		return "", processingFailure(ctx, err)
	}

	outputFile, err := os.CreateTemp(workDir, "output-*"+extension)
	if err != nil {
		return "", processingFailure(ctx, err)
	}
	outputPath = outputFile.Name()
	defer func() {
		if closeErr := outputFile.Close(); closeErr != nil && err == nil {
			err = processingFailure(ctx, closeErr)
			outputPath = ""
		}
	}()

	err = encodeImage(ctx, outputFile, format, resized)
	if err != nil {
		return "", err
	}
	return outputPath, nil
}

func encodeImage(ctx context.Context, writer io.Writer, format string, source image.Image) error {
	contextualWriter := contextWriter{ctx: ctx, writer: writer}
	var err error
	switch format {
	case "jpeg":
		err = jpeg.Encode(contextualWriter, source, nil)
	case "png":
		err = png.Encode(contextualWriter, source)
	default:
		return unsupportedDocument(errors.New("unsupported decoded image format"))
	}
	if err != nil {
		if ctx.Err() != nil {
			return processingFailure(ctx, errors.Join(err, ctx.Err()))
		}
		return processingFailure(ctx, err)
	}
	if err := ctx.Err(); err != nil {
		return processingFailure(ctx, err)
	}
	return nil
}

func imageFormatMatchesExtension(format, extension string) bool {
	switch extension {
	case ".jpg", ".jpeg":
		return format == "jpeg"
	case ".png":
		return format == "png"
	default:
		return false
	}
}

func exceedsCompressedSizeLimit(size int64) bool {
	return size > math.MaxInt32
}

func supportedExtension(path string) (string, error) {
	parsed, err := url.Parse(path)
	if err != nil {
		return "", errors.New("invalid document path")
	}
	extension := strings.ToLower(filepath.Ext(parsed.Path))
	switch extension {
	case ".pdf", ".jpg", ".jpeg", ".png":
		return extension, nil
	default:
		return "", errors.New("unsupported document extension")
	}
}

func skippedResult(extension string) store.CompressionResult {
	return store.CompressionResult{
		Status:    store.StatusSkipped,
		Extension: extension,
	}
}

func unsupportedDocument(cause error) error {
	return compression.NewDeterministicFailure(store.FailureCodeUnsupportedDocument, cause)
}

func processingFailure(ctx context.Context, cause error) error {
	if ctx != nil && ctx.Err() != nil {
		cause = errors.Join(cause, ctx.Err())
	}
	return compression.NewRetryableFailure(store.FailureCodeDatabaseUnavailable, cause)
}

func nilInterface(value any) bool {
	if value == nil {
		return true
	}
	reflected := reflect.ValueOf(value)
	switch reflected.Kind() {
	case reflect.Chan,
		reflect.Func,
		reflect.Interface,
		reflect.Map,
		reflect.Pointer,
		reflect.Slice:
		return reflected.IsNil()
	default:
		return false
	}
}

type contextReader struct {
	ctx    context.Context
	reader io.Reader
}

func (r contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	return r.reader.Read(p)
}

type contextWriter struct {
	ctx    context.Context
	writer io.Writer
}

func (w contextWriter) Write(p []byte) (int, error) {
	if err := w.ctx.Err(); err != nil {
		return 0, err
	}
	return w.writer.Write(p)
}

var _ CredentialStore = (*store.Repository)(nil)
