package azureservices

import (
	"azureocrservice/types"
	"azureocrservice/utils"
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"time"

	//"context"
	"github.com/aws/aws-sdk-go/aws"
	//"github.com/aws/aws-sdk-go-v2/config"
	//"github.com/aws/aws-sdk-go-v2/credentials"
	// "github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go/aws/credentials" // Import credentials package
	"github.com/aws/aws-sdk-go/aws/session"     // Import session package
	"github.com/aws/aws-sdk-go/service/s3/s3manager"
)

// Replace with your Azure Form Recognizer details
const (
	endpoint    = "https://foidocintelservice-test.cognitiveservices.azure.com/"
	apiKey      = "7jdjdOERNyfaULQcWmlmf6ogFcg46TmEduvDvZ3umkNYPODoPV2FJQQJ99BBACBsN54XJ3w3AAALACOGiJiJ"
	region      = "us-east-1"
	s3_endpoint = "citz-foi-prod.objectstore.gov.bc.ca" // Replace with your custom endpoint
	accessKey   = ""
	secretKey   = ""
	bucketName  = "test123"
	objectKey   = "Aparnatest/searchable.pdf"
	s3Service   = "execute-api"
)

type AzureService struct {
	SubscriptionKey string
	BaseURL         string
	Client          http.Client
}

// NewAzureService initializes a new AzureService instance
func NewAzureService(subscriptionKey string, baseURL string) *AzureService {
	return &AzureService{
		SubscriptionKey: subscriptionKey,
		BaseURL:         baseURL,
		Client: http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// // getNumPages returns the total number of pages in the given PDF file.
// func getNumPages(pdfFilePath string) (int, error) {
// 	// Open the PDF file
// 	file, err := os.Open(pdfFilePath)
// 	if err != nil {
// 		return 0, fmt.Errorf("error opening PDF: %v", err)
// 	}
// 	defer file.Close()

// 	// Use pdfcpu's Read function to get metadata
// 	ctx, err := api.ReadContextFile(file)
// 	if err != nil {
// 		return 0, fmt.Errorf("error reading PDF context: %v", err)
// 	}

// 	// Return the total page count from the PDF context
// 	return ctx.PageCount, nil
// }

// pdfToBase64 converts the entire PDF file to a Base64-encoded string.
func pdfToBase64(pdfData []byte) string {
	// Read the entire PDF file
	// pdfData, err := ioutil.ReadFile(pdfFilePath)
	// if err != nil {
	// 	return "", fmt.Errorf("error reading PDF: %v", err)
	// }

	// // Convert to Base64
	// base64PDF := base64.StdEncoding.EncodeToString(pdfData)

	// return base64PDF, nil
	return base64.StdEncoding.EncodeToString(pdfData)
}

// createSearchablePDF
func (a *AzureService) performOCR(pdfData []byte) (types.AnalyzeResults, error) {
	var results types.AnalyzeResults

	// Get the number of pages in the PDF
	// numPages, err := getNumPages(pdfFilePath)
	// if err != nil {
	// 	return err
	// }
	// fmt.Printf("Total pages in PDF: %d\n", numPages)
	// Convert pages to Base64
	base64SourceData := pdfToBase64(pdfData)
	// if err != nil {
	// 	return err
	// }
	// API request URL
	ocrPostURL := fmt.Sprintf("%s/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=2024-11-30&output=pdf", a.BaseURL)

	resultLocation, err := a.createAnalysisRequest(ocrPostURL, base64SourceData)
	if err != nil {
		return results, fmt.Errorf("failed to initiate document analysis: %w", err)
	} else {
		//wrapDocReviewerAudit(document.DocumentID, request.MinistryRequestID, resultLocation, "azureextractrequestcreated")
	}
	results, err = a.getAnalysisResults(resultLocation)
	if err != nil {
		return results, fmt.Errorf("failed to fetch analysis results: %w", err)
	}
	results, err = a.downloadSearchablePDF(resultLocation)
	fmt.Printf("Analysis Results: %v\n", results)
	return results, err
	//postURL := fmt.Sprintf("%s/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=2024-07-31-preview&output=pdf", endpoint)

	//fmt.Printf("\n StatusCode: %s\n", resp.StatusCode)

	//fmt.Printf("\n resultLocation: %s\n", resultLocation)

	//LOCAL SAVING-WORKING CODE!
	// Save the downloaded PDF
	// outputFilePath := "smudgedscanned_singlepage_searchable.pdf"
	// //outputFilePath := strings.Replace("https://citz-foi-prod.objectstore.gov.bc.ca/test123/Aparnatest/smudgedscanned_singlepage.pdf", ".pdf", "_searchable.pdf", 1)
	// fmt.Printf("\n outputFilePath: %s\n",outputFilePath)

	// pdfFile, err := os.Create(outputFilePath)
	// if err != nil {
	// 	return err
	// }
	// defer pdfFile.Close()
	// _, err = io.Copy(pdfFile, pdfResp.Body)
	// if err != nil {
	// 	return err
	// }
	// fmt.Printf("Searchable PDF saved as %s\n", outputFilePath)
	// return nil
}

func (a *AzureService) downloadSearchablePDF(resultLocation string) (types.AnalyzeResults, error) {
	var results types.AnalyzeResults
	// Construct PDF retrieval URL
	pdfURL1 := strings.Replace(resultLocation, "?api-version=2024-11-30", "", 1)
	pdfURL := pdfURL1 + "/pdf?api-version=2024-11-30"
	fmt.Printf("\n pdfURL: %s\n", pdfURL)

	// Download the searchable PDF
	pdfReq, _ := http.NewRequest("GET", pdfURL, nil)
	pdfReq.Header.Set("Ocp-Apim-Subscription-Key", apiKey)
	pdfResp, err := a.Client.Do(pdfReq)
	if err != nil {
		return results, err
	}
	defer pdfResp.Body.Close()
	// Check response status
	if pdfResp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(pdfResp.Body)
		return results, fmt.Errorf("Failed to retrieve PDF: %d %s", pdfResp.StatusCode, string(body))
	}
	pdfBody, err := io.ReadAll(pdfResp.Body)
	if err != nil {
		return results, fmt.Errorf("Failed to read PDF body: %v", err)
	}
	if len(pdfBody) == 0 {
		return results, fmt.Errorf("Empty PDF response body")
	}
	//pdfBodyReader := bytes.NewReader(pdfBody)
	err = uploadBytes(pdfBody)
	if err != nil {
		return results, err
	}

	return results, nil
}

func (a *AzureService) createAnalysisRequest(postURL string, base64SourceData string) (string, error) {

	fmt.Printf("postURL: %s\n", postURL)
	// Prepare JSON payload
	jsonPayload := fmt.Sprintf(`{"base64Source": "%s"}`, base64SourceData)
	requestBody := bytes.NewBuffer([]byte(jsonPayload))

	req, _ := http.NewRequest(http.MethodPost, postURL, requestBody)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Ocp-Apim-Subscription-Key", "7jdjdOERNyfaULQcWmlmf6ogFcg46TmEduvDvZ3umkNYPODoPV2FJQQJ99BBACBsN54XJ3w3AAALACOGiJiJ")
	resp, err := a.Client.Do(req)
	//fmt.Printf("\nresp: %s\n", resp)
	if err != nil {
		fmt.Printf("client: error making http request: %s\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	// Check for HTTP status
	if resp.StatusCode != http.StatusAccepted {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("POST request failed: %d %s", resp.StatusCode, string(body))
	}
	// Extract "Operation-Location" from headers
	resultLocation := resp.Header.Get("Operation-Location")
	if resultLocation == "" {
		return "", fmt.Errorf("Operation-Location header not found")
	}

	// apimRequestID := resp.Header.Get("Apim-Request-Id")

	// if apimRequestID == "" {
	// 	return "", fmt.Errorf("missing Apim-Request-Id in response header")
	// }
	return resultLocation, nil
}

func (a *AzureService) getAnalysisResults(resultLocation string) (types.AnalyzeResults, error) {
	// Upon successful completion, retrieve the PDF as application/pdf.
	// GET /documentModels/prebuilt-read/analyzeResults/{resultId}/pdf
	// 200 OK
	// Content-Type: application/pdf
	// Poll the GET request until the operation is complete
	var result types.AnalyzeResults
	for {
		time.Sleep(5 * time.Second) // Wait before polling
		getReq, _ := http.NewRequest("GET", resultLocation, nil)
		getReq.Header.Set("Ocp-Apim-Subscription-Key", apiKey)

		getResponse, err := a.Client.Do(getReq)
		if err != nil {
			return result, err
		}
		defer getResponse.Body.Close()

		// Read response body
		body, _ := io.ReadAll(getResponse.Body)
		if getResponse.StatusCode == http.StatusOK {
			fmt.Println("OCR processing complete")
			//wrapDocReviewerAudit(documentid, ministryrequestid, apimRequestID, "extractionsucceeded")
			break
		} else if getResponse.StatusCode == http.StatusAccepted {
			fmt.Println("Processing... Please wait.")
			//wrapDocReviewerAudit(documentid, ministryrequestid, apimRequestID, "extractionsucceeded")
			continue
		} else {
			//wrapDocReviewerAudit(documentid, ministryrequestid, apimRequestID, "extractionsucceeded")
			return result, fmt.Errorf("GET request failed: %d %s", getResponse.StatusCode, string(body))
		}
	}
	return result, nil
}

func uploadBytes(fileBytes []byte) error {
	// Create an AWS session
	sess, err := session.NewSession(&aws.Config{
		Region:           aws.String(region),
		Endpoint:         aws.String(s3_endpoint),
		Credentials:      credentials.NewStaticCredentials(accessKey, secretKey, ""),
		S3ForcePathStyle: aws.Bool(true),
	})
	if err != nil {
		log.Println("Failed to create AWS session:", err)
		return err
	}
	// Initialize S3 uploader
	uploader := s3manager.NewUploader(sess)
	// Upload the file to S3
	_, err = uploader.Upload(&s3manager.UploadInput{
		Bucket:      aws.String(bucketName),
		Key:         aws.String(objectKey),
		Body:        bytes.NewReader(fileBytes),
		ContentType: aws.String("application/pdf"), // Fix incorrect MIME type
	})
	if err != nil {
		log.Println("Failed to upload file to S3:", err)
		return err
	}
	log.Println("File uploaded successfully!")
	return nil
}

// func uploadBytes(fileBytes []byte ) (error) {
// 	// Create an AWS session
// 	sess, err := session.NewSession(&aws.Config{
// 		Region:  aws.String(region),
// 		Credentials: credentials.NewStaticCredentials(accessKey, secretKey, ""),
// 	})
// 	if err != nil {
// 		log.Println("Failed to create AWS session:", err)
// 		return err
// 	}
// 	// Prepare the S3 URI
// 	s3URI := fmt.Sprintf("https://%s/%s/%s", s3_endpoint, bucketName, objectKey)
// 	log.Println("\ns3URI:", s3URI)
// 	// Create a new HTTP PUT request
// 	req, err := http.NewRequest("PUT", s3URI, bytes.NewReader(fileBytes))
// 	if err != nil {
// 		log.Println("Failed to create request:", err)
// 		return err
// 	}
// 	// Add headers to the request
// 	req.Header.Set("Content-Type", "application/pdf")
// 	req.Header.Set("x-amz-date", time.Now().UTC().Format("20060102T150405Z"))

// 	// AWS Signature v4 signing process
// 	signer := v4.NewSigner(sess.Config.Credentials)
// 	_, err = signer.Sign(req, bytes.NewReader(fileBytes), s3Service, region, time.Now())
// 	if err != nil {
// 		log.Println("Failed to sign request:", err)
// 		return err
// 	}
// 	// Upload the file to S3
// 	resp, err := http.DefaultClient.Do(req)
// 	if err != nil {
// 		log.Println("Failed to upload file to S3:", err)
// 		return err
// 	}
// 	defer resp.Body.Close()
// 	// Read the response body (optional for debugging purposes)
// 	respBody, _ := ioutil.ReadAll(resp.Body)
// 	fmt.Printf("Response: %s\n", respBody)
// 	// Check if the upload was successful
// 	if resp.StatusCode != http.StatusOK {
// 		log.Println("Failed to upload to S3:", resp.Status)
// 		return fmt.Errorf("Failed to upload file: %s", resp.Status)
// 	}
// 	return nil
// }

// func uploadToS3(pdfBody io.Reader) error {

// 	// Load AWS configuration with custom endpoint and credentials
// 	cfg, err := config.LoadDefaultConfig(
// 		context.Background(),
// 		config.WithRegion(region),
// 		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
// 		config.WithEndpointResolver(aws.EndpointResolverFunc(func(service, region string) (aws.Endpoint, error) {
// 			return aws.Endpoint{
// 				URL:  s3_endpoint,
// 				HostnameImmutable: true,
// 			}, nil
// 		})),
// 	)
// 	if err != nil {
// 		log.Fatalf("unable to load SDK config, %v", err)
// 	}

// 	// Create S3 client
// 	s3Client := s3.NewFromConfig(cfg)
// 	fmt.Printf("\ns3Client: %s\n",s3Client)
// 	fmt.Printf("\nbkt: %s\n",bucketName)
// 	fmt.Printf("\nkey: %s\n",objectKey)

// 	// Upload the PDF to the S3-compatible storage
// 	_, err = s3Client.PutObject(context.Background(), &s3.PutObjectInput{
// 		Bucket:  aws.String(bucketName),
// 		Key:   aws.String(objectKey),
// 		Body:   pdfBody,
// 		ContentType: aws.String("application/pdf"),
// 	})
// 	if err != nil {
// 		log.Fatalf("unable to upload object, %v", err)
// 	}

// 	fmt.Println("PDF uploaded successfully to S3-compatible storage.")
// 	return nil
// }

// func DownloadFile(url string) ([]byte, error) {
// 	// Send an HTTP GET request to the URL
// 	resp, err := http.Get(url)
// 	if err != nil {
// 		return nil, fmt.Errorf("error downloading file: %v", err)
// 	}
// 	defer resp.Body.Close()

// 	// Read the file data into a byte slice
// 	data, err := ioutil.ReadAll(resp.Body)
// 	if err != nil {
// 		return nil, fmt.Errorf("error reading downloaded file: %v", err)
// 	}

// 	return data, nil
// }

func CallAzureOCRService(pdfData []byte) (types.AnalyzeResults, error) {
	// Load environment variables
	// azureEndpoint := os.Getenv("AZURE_ENDPOINT")
	// azureAPIKey := os.Getenv("AZURE_API_KEY")
	// Specify the PDF file
	//pdfFilePath := "https://citz-foi-prod.objectstore.gov.bc.ca/test123/Aparnatest/smudgedscanned_singlepage.pdf"

	// pdfData, err := DownloadFile(pdfFilePath)
	// if err != nil {
	// 	fmt.Println("Error downloading PDF:", err)
	// 	return
	// }
	subscriptionKey := utils.ViperEnvVariable("azuresubcriptionkey")
	baseURL := utils.ViperEnvVariable("azuredocumentocraiendpoint")

	service := NewAzureService(subscriptionKey, baseURL)
	// Run the function
	result, err := service.performOCR(pdfData)
	if err != nil {
		fmt.Println("Error:", err)
	}
	return result, err
}
