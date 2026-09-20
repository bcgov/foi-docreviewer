package s3services

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"path/filepath"
	"strings"
	"time"

	"azureocrservice/types"
	"azureocrservice/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

func GenerateDownloadPresignedURL(s3relativefileurl string) (string, error) {
	s3Details, err := GetS3Details(s3relativefileurl)
	if err != nil {
		return "", fmt.Errorf("s3 details for download: %w", err)
	}
	// Create a new session with the provided credentials
	sess, err := session.NewSession(&aws.Config{
		Region:      aws.String(s3Details.Region),
		Endpoint:    aws.String(s3Details.EndPoint), // S3-compatible endpoint (like S3 Browser)
		Credentials: credentials.NewStaticCredentials(s3Details.AccessKey, s3Details.SecretKey, ""),
	})
	if err != nil {
		return "", fmt.Errorf("failed to create session: %v", err)
	}
	// Create a new S3 client
	svc := s3.New(sess)
	// Prepare the GetObjectRequest
	req, _ := svc.GetObjectRequest(&s3.GetObjectInput{
		Bucket: aws.String(s3Details.BucketName),
		Key:    aws.String(s3Details.ObjectKey),
	})
	// Generate the presigned URL
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
		//fmt.Println("Error in parsing URL")
		return S3Details, fmt.Errorf("error in parsing URL: %v", err)
	}
	relativePath := parsedURL.Path
	relativePath = strings.TrimPrefix(relativePath, "/")
	bucketname, relativePath, found := strings.Cut(relativePath, "/")
	if !found {
		//fmt.Println("Invalid URL format")
		return S3Details, fmt.Errorf("invalid URL format")
	}
	//fmt.Printf("Bucket: %s, Key: %s\n", bucketname, relativePath)
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
	OCRKey := OCRKeyFor(s3Details.ObjectKey)
	// Create a new AWS session with credentials and config
	sess, err := session.NewSession(&aws.Config{
		Region:           aws.String(s3Details.Region),
		Endpoint:         aws.String(s3Details.EndPoint),
		Credentials:      credentials.NewStaticCredentials(s3Details.AccessKey, s3Details.SecretKey, ""),
		S3ForcePathStyle: aws.Bool(true), // Often needed for S3-compatible endpoints
	})
	if err != nil {
		return "", fmt.Errorf("failed to create AWS session: %v", err)
	}
	// Create an S3 client
	svc := s3.New(sess)
	// Create a presigned PUT request
	req, _ := svc.PutObjectRequest(&s3.PutObjectInput{
		Bucket: aws.String(s3Details.BucketName),
		Key:    aws.String(OCRKey),
	})
	// Generate presigned URL
	presignedURL, err := req.Presign(s3Details.Expiry)
	if err != nil {
		return "", fmt.Errorf("failed to presign PUT request: %v", err)
	}
	return presignedURL, nil
}

// UploadUsingPresignedURL PUTs fileData to a presigned URL with the caller's
// client (which carries the timeout). The URL is never logged: it embeds credentials.
func UploadUsingPresignedURL(client *http.Client, presignedURL string, fileData []byte) error {
	req, err := http.NewRequest(http.MethodPut, presignedURL, bytes.NewReader(fileData))
	if err != nil {
		return fmt.Errorf("failed to create request: %v", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to upload to S3 using presigned URL: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("upload failed with status %d: %s", resp.StatusCode, string(body))
	}
	return nil
}
