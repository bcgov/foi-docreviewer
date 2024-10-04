package s3services

import (
	"fmt"
	"io"
	"log"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/s3"
	"github.com/spf13/viper"
)

// use viper package to read .env file
// return the value of the key
func viperEnvVariable(key string) string {

	// SetConfigFile explicitly defines the path, name and extension of the config file.
	// Viper will use this and not check any of the config paths.
	// .env - It will search for the .env file in the current directory
	viper.SetConfigFile("./.env")

	// Find and read the config file
	err := viper.ReadInConfig()

	if err != nil {
		log.Fatalf("Error while reading config file %s", err)
	}

	// viper.Get() returns an empty interface{}
	// to get the underlying type of the key,
	// we have to do the type assertion, we know the underlying value is string
	// if we type assert to other type it will throw an error
	value, ok := viper.Get(key).(string)

	// If the type is a string then ok will be true
	// ok will make sure the program not break
	if !ok {
		log.Fatalf("Invalid type assertion")
	}

	return value
}

func GetFilefroms3(s3fileurl string) []byte {
	// Define S3-compatible storage endpoint and credentials
	s3Endpoint := viperEnvVariable("s3endpoint") // Update with your S3-compatible endpoint
	accessKey := viperEnvVariable("accesskey")
	secretKey := viperEnvVariable("secretkey")
	bucketName := "/test123-protected/"
	objectKey := "/test-event-2022/potluck-23-mar-2022.pdf"
	region := "us-east-1" // e.g., "us-east-1"

	// Set up a session with the S3-compatible storage
	sess, err := session.NewSession(&aws.Config{
		Region:           aws.String(region),
		Endpoint:         aws.String(s3Endpoint),
		Credentials:      credentials.NewStaticCredentials(accessKey, secretKey, ""),
		S3ForcePathStyle: aws.Bool(true), //ABIN: THIS IS VERY IMPORTANT to override AWS S3 style.
	})
	if err != nil {
		fmt.Println("Failed to create S3 session:", err)
		return nil
	}

	// Create an S3 service client
	svc := s3.New(sess)

	// Define the input for GetObject
	input := &s3.GetObjectInput{
		Bucket: aws.String(bucketName),
		Key:    aws.String(objectKey),
	}

	// Call GetObject to download the file
	result, err := svc.GetObject(input)
	if err != nil {
		fmt.Println("Failed to download file:", err)
		return nil
	}
	defer result.Body.Close()

	filebytes, err := io.ReadAll(result.Body)
	if err != nil {
		log.Print(err)
	}

	fmt.Println("Eength of bytes:", len(filebytes))

	return filebytes
}
