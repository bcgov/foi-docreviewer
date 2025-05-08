package s3services

import (
	"fmt"
	"log"
	"time"

	"azuredocextractservice/utils"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
)

func GetFilefroms3(s3relativefileurl string, bucketname string) string {
	// Define S3-compatible storage endpoint and credentials
	endpoint := utils.ViperEnvVariable("s3endpoint") // Update with your S3-compatible endpoint
	accessKey := utils.ViperEnvVariable("s3accesskey")
	secretKey := utils.ViperEnvVariable("s3secretkey")
	bucketName := "/" + bucketname + "/"
	objectKey := s3relativefileurl
	region := utils.ViperEnvVariable("s3region") // e.g., "us-east-1"
	//s3forcepathstyle, _ := strconv.ParseBool(utils.ViperEnvVariable("s3forcepathstyle"))
	expiry := 15 * time.Minute // Presigned URL expiry time
	url, err := generatePresignedURL(endpoint, accessKey, secretKey, bucketName, objectKey, region, expiry)
	if err != nil {
		log.Fatalf("Error generating presigned URL: %v", err)
	}

	fmt.Println("Presigned URL:", url)
	return url
}

func generatePresignedURL(endpoint, accessKey, secretKey, bucketName, objectKey, region string, expiry time.Duration) (string, error) {
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
