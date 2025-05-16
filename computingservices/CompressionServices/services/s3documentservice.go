package services

import (
	"compressionservices/models"
	"compressionservices/utils"
	"database/sql"
	"fmt"
	"log"
	"path/filepath"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
	_ "github.com/lib/pq"
)

func GetCredentialsByBCGovCode(bcgovcode string) (*models.S3Credentials, string, error) {
	db := utils.GetDBConnection()
	defer db.Close()

	query := `
		SELECT attributes
		FROM public."DocumentPathMapper"
		WHERE bucket = $1 AND category = 'Records'
	`
	bucket := fmt.Sprintf("%s-%s-e", strings.ToLower(bcgovcode), strings.ToLower(utils.ViperEnvVariable("COMPRESSION_S3_ENV")))
	row := db.QueryRow(query, bucket)

	var attributes string
	err := row.Scan(&attributes)
	if err != nil {
		if err == sql.ErrNoRows {
			log.Printf("No rows found for bucket: %s", bucket)
		} else {
			log.Printf("Query error: %v", err)
		}
		return nil, "", err
	}

	s3cred, err := utils.GetS3CredentialsObject(attributes)
	if err != nil {
		log.Printf("Error parsing S3 credentials: %v", err)
		return nil, "", err
	}

	return s3cred, bucket, nil
}

func GetFilefroms3(message *models.CompressionProducerMessage) (string, *models.S3Credentials, string, error) {
	s3cred, bucketname, err := GetCredentialsByBCGovCode(message.BCGovCode)
	if err != nil {
		log.Fatalf("Failed to process folder: %v", err)
	}
	// Define S3-compatible storage endpoint and credentials
	endpoint := utils.ViperEnvVariable("COMPRESSION_S3_HOST") // Update with your S3-compatible endpoint
	accessKey := s3cred.S3AccessKey
	secretKey := s3cred.S3SecretKey
	bucketName := "/" + bucketname + "/"
	objectKey := message.S3FilePath
	region := utils.ViperEnvVariable("COMPRESSION_S3_REGION") // e.g., "us-east-1"
	//s3forcepathstyle, _ := strconv.ParseBool(utils.ViperEnvVariable("s3forcepathstyle"))
	expiry := 15 * time.Minute // Presigned URL expiry time
	url, err := generatePresignedURL(endpoint, accessKey, secretKey, bucketName, objectKey, region, expiry)
	if err != nil {
		log.Fatalf("Error generating presigned URL: %v", err)
	}
	//fmt.Println("\nPresigned URL:", url)
	return url, s3cred, bucketname, err
}

func generatePresignedURL(endpoint, accessKey, secretKey, bucketName, fullFilePath, region string, expiry time.Duration) (string, error) {
	//fmt.Printf("fullFilePath: %s\n", fullFilePath)
	objectKey := strings.SplitN(fullFilePath, bucketName, 2)[1]
	// fmt.Println("Object Key:", objectKey)

	// Create a new session with the provided credentials
	sess, err := session.NewSession(&aws.Config{
		Region:      aws.String(region),
		Endpoint:    aws.String(endpoint), // S3-compatible endpoint (like S3 Browser)
		Credentials: credentials.NewStaticCredentials(accessKey, secretKey, ""),
	})
	if err != nil {
		return "", fmt.Errorf("failed to create session: %v", err)
	}
	// Create a new S3 client
	svc := s3.New(sess)
	// Prepare the GetObjectRequest
	req, _ := svc.GetObjectRequest(&s3.GetObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
	})
	// Generate the presigned URL
	presignedURL, err := req.Presign(expiry)
	if err != nil {
		return "", fmt.Errorf("failed to generate presigned URL: %v", err)
	}
	return presignedURL, nil
}

func generatePresignedUploadURL(endpoint, accessKey, secretKey, bucketName, fullFilePath, region string, expiry time.Duration) (string, error) {
	objectKey := strings.SplitN(fullFilePath, bucketName, 2)[1]
	//fmt.Println("Object Key:", objectKey)
	ext := filepath.Ext(objectKey)             // e.g. ".pdf"
	name := strings.TrimSuffix(objectKey, ext) // e.g. "/some/path/file"
	compressedKey := name + "COMPRESSED" + ext // e.g. "/some/path/file-compressed.pdf"
	//fmt.Println("Compressed Object Key:", compressedKey)
	// Create a new AWS session with credentials and config
	sess, err := session.NewSession(&aws.Config{
		Region:           aws.String(region),
		Endpoint:         aws.String(endpoint),
		Credentials:      credentials.NewStaticCredentials(accessKey, secretKey, ""),
		S3ForcePathStyle: aws.Bool(true), // Often needed for S3-compatible endpoints
	})
	if err != nil {
		return "", fmt.Errorf("failed to create AWS session: %v", err)
	}
	// Create an S3 client
	svc := s3.New(sess)
	// Create a presigned PUT request
	req, _ := svc.PutObjectRequest(&s3.PutObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(compressedKey),
	})
	// Generate presigned URL
	presignedURL, err := req.Presign(expiry)
	if err != nil {
		return "", fmt.Errorf("failed to presign PUT request: %v", err)
	}
	return presignedURL, nil
}
