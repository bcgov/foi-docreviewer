package compressor

import (
	"context"
	"errors"
	"net/url"
	"path"
	"strings"
	"time"
	"unicode"

	"compressionservices/models"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

const legacyPresignExpiry = 15 * time.Minute

var (
	errInvalidS3Configuration = errors.New("invalid s3 signer configuration")
	errInvalidS3Object        = errors.New("invalid s3 object")
)

// AWSSigner presigns S3-compatible GET and PUT operations.
type AWSSigner struct {
	endpoint string
	region   string
	expiry   time.Duration
}

// NewAWSSigner creates a signer after validating its security-sensitive
// endpoint and presign lifetime.
func NewAWSSigner(endpoint, region string, expiry time.Duration) (*AWSSigner, error) {
	endpoint, err := validatedEndpoint(endpoint)
	if err != nil || strings.TrimSpace(region) == "" || expiry <= 0 || expiry > legacyPresignExpiry {
		return nil, errInvalidS3Configuration
	}
	return &AWSSigner{
		endpoint: endpoint,
		region:   strings.TrimSpace(region),
		expiry:   expiry,
	}, nil
}

// DownloadURL returns a presigned GET URL for objectPath.
func (s *AWSSigner) DownloadURL(
	ctx context.Context,
	s3Credentials models.S3Credentials,
	bucket string,
	objectPath string,
) (string, error) {
	if err := s.validate(ctx, s3Credentials, bucket); err != nil {
		return "", err
	}
	objectKey, err := objectKey(bucket, objectPath)
	if err != nil {
		return "", err
	}

	client, err := s.client(s3Credentials)
	if err != nil {
		return "", err
	}
	request, _ := client.GetObjectRequest(&s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(objectKey),
	})
	request.SetContext(ctx)
	presignedURL, err := request.Presign(s.expiry)
	if err != nil {
		return "", errors.New("creating s3 download signature failed")
	}
	if err := ctx.Err(); err != nil {
		return "", err
	}
	return presignedURL, nil
}

// UploadURL returns a presigned PUT URL and its query-free stored object path.
func (s *AWSSigner) UploadURL(
	ctx context.Context,
	s3Credentials models.S3Credentials,
	bucket string,
	objectPath string,
) (string, string, error) {
	if err := s.validate(ctx, s3Credentials, bucket); err != nil {
		return "", "", err
	}
	objectKey, err := objectKey(bucket, objectPath)
	if err != nil {
		return "", "", err
	}
	compressedKey, err := compressedObjectKey(objectKey)
	if err != nil {
		return "", "", err
	}

	client, err := s.client(s3Credentials)
	if err != nil {
		return "", "", err
	}
	request, _ := client.PutObjectRequest(&s3.PutObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(compressedKey),
	})
	request.SetContext(ctx)
	presignedURL, err := request.Presign(s.expiry)
	if err != nil {
		return "", "", errors.New("creating s3 upload signature failed")
	}
	if err := ctx.Err(); err != nil {
		return "", "", err
	}
	sanitizedPath, err := removeURLQuery(presignedURL)
	if err != nil {
		return "", "", err
	}
	return presignedURL, sanitizedPath, nil
}

func (s *AWSSigner) validate(
	ctx context.Context,
	s3Credentials models.S3Credentials,
	bucket string,
) error {
	if ctx == nil {
		return errInvalidS3Configuration
	}
	if err := ctx.Err(); err != nil {
		return err
	}
	if s == nil ||
		s.region == "" ||
		s.expiry <= 0 ||
		s.expiry > legacyPresignExpiry ||
		strings.TrimSpace(bucket) == "" ||
		strings.TrimSpace(s3Credentials.S3AccessKey) == "" ||
		strings.TrimSpace(s3Credentials.S3SecretKey) == "" {
		return errInvalidS3Configuration
	}
	if _, err := validatedEndpoint(s.endpoint); err != nil {
		return errInvalidS3Configuration
	}
	return nil
}

func (s *AWSSigner) client(s3Credentials models.S3Credentials) (*s3.S3, error) {
	awsSession, err := session.NewSession(aws.NewConfig().
		WithRegion(s.region).
		WithEndpoint(s.endpoint).
		WithS3ForcePathStyle(true).
		WithCredentials(credentials.NewStaticCredentials(
			s3Credentials.S3AccessKey,
			s3Credentials.S3SecretKey,
			"",
		)))
	if err != nil {
		return nil, errors.New("creating s3 signer failed")
	}
	return s3.New(awsSession), nil
}

func objectKey(bucket, objectPath string) (string, error) {
	bucket = strings.TrimSpace(bucket)
	rawObjectPath := strings.TrimSpace(objectPath)
	if bucket == "" || rawObjectPath == "" {
		return "", errInvalidS3Object
	}

	parsed, err := url.Parse(rawObjectPath)
	if err != nil {
		return "", errInvalidS3Object
	}
	if parsed.User != nil ||
		parsed.RawQuery != "" ||
		parsed.ForceQuery ||
		strings.Contains(rawObjectPath, "#") {
		return "", errInvalidS3Object
	}

	var key string
	switch parsed.Scheme {
	case "":
		if parsed.Host != "" || strings.HasPrefix(rawObjectPath, "/") {
			return "", errInvalidS3Object
		}
		key = parsed.Path
	case "s3":
		if parsed.Host != bucket {
			return "", errInvalidS3Object
		}
		key = strings.TrimPrefix(parsed.Path, "/")
	case "http", "https":
		if parsed.Host == "" {
			return "", errInvalidS3Object
		}
		bucketPrefix := "/" + bucket + "/"
		if !strings.HasPrefix(parsed.Path, bucketPrefix) {
			return "", errInvalidS3Object
		}
		key = strings.TrimPrefix(parsed.Path, bucketPrefix)
	default:
		return "", errInvalidS3Object
	}
	if !validObjectKey(key) {
		return "", errInvalidS3Object
	}
	return key, nil
}

func validObjectKey(key string) bool {
	if key == "" {
		return false
	}
	for _, segment := range strings.Split(key, "/") {
		if segment == "." || segment == ".." {
			return false
		}
		for _, character := range segment {
			if unicode.IsControl(character) {
				return false
			}
		}
	}
	return true
}

func compressedObjectKey(objectKey string) (string, error) {
	extension := path.Ext(objectKey)
	if extension == "" {
		return "", errInvalidS3Object
	}
	return strings.TrimSuffix(objectKey, extension) + "COMPRESSED" + extension, nil
}

func removeURLQuery(rawURL string) (string, error) {
	parsed, err := url.Parse(rawURL)
	if err != nil ||
		(parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Host == "" ||
		parsed.User != nil {
		return "", errInvalidS3Object
	}
	parsed.RawQuery = ""
	parsed.ForceQuery = false
	parsed.Fragment = ""
	return parsed.String(), nil
}

func validatedEndpoint(rawEndpoint string) (string, error) {
	parsed, err := url.Parse(strings.TrimSpace(rawEndpoint))
	if err != nil ||
		(parsed.Scheme != "http" && parsed.Scheme != "https") ||
		parsed.Host == "" ||
		parsed.User != nil ||
		parsed.RawQuery != "" ||
		parsed.ForceQuery ||
		strings.Contains(strings.TrimSpace(rawEndpoint), "#") {
		return "", errInvalidS3Configuration
	}
	return parsed.String(), nil
}
