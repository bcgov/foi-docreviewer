package s3services

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"azureocrservice/httpx"
	"azureocrservice/logx"
	"azureocrservice/types"
	"azureocrservice/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

// Sessions are built once per (pathStyle) variant: the download presign has
// always used virtual-host style and the upload presign path style, and both
// work against the current endpoints, so that asymmetry is preserved.
var (
	sessMu   sync.Mutex
	sessions = map[bool]*session.Session{}
)

func awsSession(d types.S3Details, pathStyle bool) (*session.Session, error) {
	sessMu.Lock()
	defer sessMu.Unlock()
	if s, ok := sessions[pathStyle]; ok {
		return s, nil
	}
	s, err := session.NewSession(&aws.Config{
		Region:           aws.String(d.Region),
		Endpoint:         aws.String(d.EndPoint),
		Credentials:      credentials.NewStaticCredentials(d.AccessKey, d.SecretKey, ""),
		S3ForcePathStyle: aws.Bool(pathStyle),
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %v", err)
	}
	sessions[pathStyle] = s
	return s, nil
}

func GenerateDownloadPresignedURL(s3relativefileurl string) (string, error) {
	s3Details, err := GetS3Details(s3relativefileurl)
	if err != nil {
		return "", fmt.Errorf("s3 details for download: %w", err)
	}
	sess, err := awsSession(s3Details, false)
	if err != nil {
		return "", err
	}
	req, _ := s3.New(sess).GetObjectRequest(&s3.GetObjectInput{
		Bucket: aws.String(s3Details.BucketName),
		Key:    aws.String(s3Details.ObjectKey),
	})
	presignedURL, err := req.Presign(s3Details.Expiry)
	if err != nil {
		return "", fmt.Errorf("failed to generate presigned URL: %v", err)
	}
	return presignedURL, nil
}

// OCRKeyFor returns the object key of the searchable PDF written next to the
// source object: the extension is kept and "OCR" is inserted before it.
func OCRKeyFor(objectKey string) string {
	ext := filepath.Ext(objectKey)
	return strings.TrimSuffix(objectKey, ext) + "OCR" + ext
}

func GetS3Details(s3FilePath string) (types.S3Details, error) {
	S3Details := types.S3Details{}
	parsedURL, err := url.Parse(s3FilePath)
	if err != nil {
		return S3Details, fmt.Errorf("error in parsing URL: %v", err)
	}
	relativePath := parsedURL.Path
	relativePath = strings.TrimPrefix(relativePath, "/")
	bucketname, relativePath, found := strings.Cut(relativePath, "/")
	if !found {
		return S3Details, fmt.Errorf("invalid URL format")
	}
	S3Details = types.S3Details{
		EndPoint:   utils.ViperEnvVariable("s3endpoint"),
		AccessKey:  utils.ViperEnvVariable("s3accesskey"),
		SecretKey:  utils.ViperEnvVariable("s3secretkey"),
		BucketName: "/" + bucketname + "/",
		ObjectKey:  relativePath,
		Region:     utils.ViperEnvVariable("s3region"), // e.g., "us-east-1"
		Expiry:     15 * time.Minute,
	}
	return S3Details, nil
}

func GeneratePresignedUploadURL(fullFilePath string) (string, error) {
	s3Details, s3Err := GetS3Details(fullFilePath)
	if s3Err != nil {
		return "", fmt.Errorf("error in s3 details: %v", s3Err)
	}
	sess, err := awsSession(s3Details, true)
	if err != nil {
		return "", err
	}
	req, _ := s3.New(sess).PutObjectRequest(&s3.PutObjectInput{
		Bucket: aws.String(s3Details.BucketName),
		Key:    aws.String(OCRKeyFor(s3Details.ObjectKey)),
	})
	presignedURL, err := req.Presign(s3Details.Expiry)
	if err != nil {
		return "", fmt.Errorf("failed to presign PUT request: %v", err)
	}
	return presignedURL, nil
}

// Store is the pipeline's view of S3: presigned GET/PUT through one retrying client.
type Store struct {
	http   *http.Client
	policy httpx.RetryPolicy
}

func NewStore(timeout time.Duration, policy httpx.RetryPolicy) *Store {
	return &Store{http: &http.Client{Timeout: timeout}, policy: policy}
}

func (s *Store) PresignGet(s3path string) (string, error) {
	u, err := GenerateDownloadPresignedURL(s3path)
	if err != nil {
		return "", httpx.Coded("Presign", 0, err)
	}
	return u, nil
}

func (s *Store) Download(ctx context.Context, docID int64, s3path string) ([]byte, error) {
	u, err := s.PresignGet(s3path)
	if err != nil {
		return nil, err
	}
	return s.DownloadFrom(ctx, docID, u)
}

func (s *Store) DownloadFrom(ctx context.Context, docID int64, presignedURL string) ([]byte, error) {
	build := func(ctx context.Context) (*http.Request, error) {
		return http.NewRequestWithContext(ctx, http.MethodGet, presignedURL, nil)
	}
	start := time.Now()
	resp, attempts, err := httpx.DoWithRetry(ctx, s.http, build, s.policy, "S3", "documentid", docID, "stage", "download")
	if err != nil {
		return nil, httpx.Coded("Transport", attempts, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, httpx.Coded(fmt.Sprintf("HTTP%d", resp.StatusCode), attempts, fmt.Errorf("download status %d", resp.StatusCode))
	}
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, httpx.Coded("Transport", attempts, err)
	}
	if len(data) == 0 {
		return nil, httpx.Coded("EmptyObject", attempts, errors.New("source object is empty"))
	}
	logx.Event("DOWNLOAD_OK", "documentid", docID, "bytes", len(data), "ms", logx.Ms(start))
	return data, nil
}

func (s *Store) Upload(ctx context.Context, docID int64, s3path string, pdf []byte) (string, int, error) {
	u, err := GeneratePresignedUploadURL(s3path)
	if err != nil {
		return "", 0, httpx.Coded("Presign", 0, err)
	}
	size, err := s.UploadTo(ctx, docID, u, pdf)
	if err != nil {
		return "", 0, err
	}
	key := strings.SplitN(u, "?", 2)[0]
	logx.Event("UPLOAD_OK", "documentid", docID, "key", key, "bytes", size)
	return key, size, nil
}

func (s *Store) UploadTo(ctx context.Context, docID int64, presignedURL string, pdf []byte) (int, error) {
	build := func(ctx context.Context) (*http.Request, error) {
		return http.NewRequestWithContext(ctx, http.MethodPut, presignedURL, bytes.NewReader(pdf))
	}
	resp, attempts, err := httpx.DoWithRetry(ctx, s.http, build, s.policy, "S3", "documentid", docID, "stage", "upload")
	if err != nil {
		return 0, httpx.Coded("Transport", attempts, err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 2048))
		return 0, httpx.Coded(fmt.Sprintf("HTTP%d", resp.StatusCode), attempts, fmt.Errorf("upload status %d: %s", resp.StatusCode, body))
	}
	return len(pdf), nil
}
