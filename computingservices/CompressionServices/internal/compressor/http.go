package compressor

import (
	"context"
	"errors"
	"io"
	"net/http"

	"compressionservices/internal/compression"
	"compressionservices/internal/store"
)

const (
	maxErrorBodyBytes  = 4 * 1024
	httpCopyBufferSize = 64 * 1024
)

func download(
	ctx context.Context,
	client *http.Client,
	requestURL string,
	destination io.Writer,
) error {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, requestURL, nil)
	if err != nil {
		return downloadFailure(err)
	}

	response, err := client.Do(request)
	if err != nil {
		return downloadFailure(contextCause(ctx, err))
	}
	defer func() {
		_ = response.Body.Close()
	}()

	if !successStatus(response.StatusCode) {
		discardBounded(response.Body)
		return downloadFailure(errors.New("download returned non-success status"))
	}

	buffer := make([]byte, httpCopyBufferSize)
	if _, err := io.CopyBuffer(destination, response.Body, buffer); err != nil {
		return downloadFailure(contextCause(ctx, err))
	}
	if err := ctx.Err(); err != nil {
		return downloadFailure(err)
	}
	return nil
}

func upload(
	ctx context.Context,
	client *http.Client,
	requestURL string,
	source io.Reader,
	contentLength int64,
) error {
	if contentLength < 0 {
		return uploadFailure(errors.New("upload content length is invalid"))
	}
	// Keep ownership of production *os.File values with the caller. The HTTP
	// transport closes only this wrapper while reading the file incrementally.
	body := struct{ io.Reader }{Reader: source}
	request, err := http.NewRequestWithContext(ctx, http.MethodPut, requestURL, body)
	if err != nil {
		return uploadFailure(err)
	}
	request.ContentLength = contentLength

	response, err := client.Do(request)
	if err != nil {
		return uploadFailure(contextCause(ctx, err))
	}
	defer func() {
		_ = response.Body.Close()
	}()

	if !successStatus(response.StatusCode) {
		discardBounded(response.Body)
		return uploadFailure(errors.New("upload returned non-success status"))
	}
	discardBounded(response.Body)
	if err := ctx.Err(); err != nil {
		return uploadFailure(err)
	}
	return nil
}

func successStatus(statusCode int) bool {
	return statusCode >= http.StatusOK && statusCode < http.StatusMultipleChoices
}

func discardBounded(body io.Reader) {
	_, _ = io.Copy(io.Discard, io.LimitReader(body, maxErrorBodyBytes))
}

func contextCause(ctx context.Context, cause error) error {
	if err := ctx.Err(); err != nil {
		return errors.Join(err, cause)
	}
	return cause
}

func downloadFailure(cause error) error {
	return compression.NewRetryableFailure(store.FailureCodeS3DownloadTimeout, cause)
}

func uploadFailure(cause error) error {
	return compression.NewRetryableFailure(store.FailureCodeS3UploadFailed, cause)
}
