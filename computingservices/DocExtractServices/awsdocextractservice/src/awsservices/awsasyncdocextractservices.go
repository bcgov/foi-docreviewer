package awsservices

import (
	"fmt"
	"log"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/textract"
)

//var foitextractStartDocumentTextDetectionInput *textract.StartDocumentTextDetectionInput

func init() {

	awsaccesskey := viperEnvVariable("awsaccesskey")
	awssecret := viperEnvVariable("awssecret")
	awstoken := viperEnvVariable("awstoken")

	textractSession = textract.New(session.Must(session.NewSession(&aws.Config{
		Region:      aws.String("ca-central-1"),
		Credentials: credentials.NewStaticCredentials(awsaccesskey, awssecret, awstoken),
	})))
}

func ExtractdocumentcontentAsync(filename string) {

	// Define the input for the StartDocumentTextDetection API
	input := &textract.StartDocumentTextDetectionInput{
		DocumentLocation: &textract.DocumentLocation{
			S3Object: &textract.S3Object{
				Bucket: aws.String("foiprocessingbucket"), // Replace with your S3 bucket
				Name:   aws.String(filename),              // Replace with your document's key (file name)
			},
		},
		NotificationChannel: &textract.NotificationChannel{
			RoleArn:     aws.String("arn:aws:iam::010928225293:role/FOITextractRole"),                         // Replace with your IAM Role ARN
			SNSTopicArn: aws.String("arn:aws:sns:ca-central-1:010928225293:AmazonTextractTopic1722637179517"), // Replace with your SNS topic ARN
		},
	}

	// Start the document text detection job
	resp, err := textractSession.StartDocumentTextDetection(input)
	if err != nil {
		fmt.Printf("Failed to start document text detection: %v", err)
	}

	// Output the JobId
	fmt.Printf("Job started with JobId: %s\n", *resp.JobId)

	// Poll until the job is finished
	status := checkJobStatus(*resp.JobId)

	// If the job succeeded, retrieve the results
	if status == string("SUCCEEDED") {
		getTextDetectionResults(*resp.JobId)
	} else {
		fmt.Println("The job did not complete successfully.")
	}

}

func getTextDetectionResults(jobId string) {

	input := &textract.GetDocumentTextDetectionInput{
		JobId: aws.String(jobId),
	}

	// Get the document text detection results
	resp, err := textractSession.GetDocumentTextDetection(input)
	if err != nil {
		log.Fatalf("Failed to retrieve document text detection results: %v", err)
	}

	// Print out the detected text
	for _, block := range resp.Blocks {
		if string(*block.BlockType) == string("LINE") {
			fmt.Printf("Detected Text: %s\n", string(*block.Text))
		}

	}
}

func checkJobStatus(jobId string) string {
	returnVal := ""
	nexttoken := ""
	input := &textract.GetDocumentTextDetectionInput{
		JobId:      aws.String(jobId),
		MaxResults: aws.Int64(1000),
	}
	for returnVal == "" {
		if nexttoken != "" {
			input = &textract.GetDocumentTextDetectionInput{
				JobId:      aws.String(jobId),
				MaxResults: aws.Int64(1000),
				NextToken:  aws.String(nexttoken),
			}
		}

		// Call the GetDocumentTextDetection API to check the job status
		resp, err := textractSession.GetDocumentTextDetection(input)
		if err != nil {
			fmt.Printf("Failed to check document text detection status: %v", err)
		}

		if *resp.JobStatus == "SUCCEEDED" || *resp.JobStatus == "FAILED" {
			fmt.Printf("Job Status info received as : %s\n", *resp.JobStatus)
			returnVal = *resp.JobStatus

		} else {
			fmt.Printf("Job Status seems to be: %s\n", *resp.JobStatus)
			fmt.Println("Job is still in progress. Waiting...")
			// Wait before checking the status again
			//time.Sleep(5) // Adjust the polling interval as needed
		}

	}

	return returnVal

}
