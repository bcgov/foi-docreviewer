package azureservices

import (
	"azureocrservice/docreviewerocrservice"
	"azureocrservice/s3services"
	"azureocrservice/types"
	"azureocrservice/utils"
	"bytes"
	"encoding/base64"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
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

// pdfToBase64 converts the entire PDF file to a Base64-encoded string.
func pdfToBase64(pdfData []byte) string {
	return base64.StdEncoding.EncodeToString(pdfData)
}

// createSearchablePDF
func (a *AzureService) performOCR(pdfData []byte, message types.QueueMessage) (types.AnalyzeResults, error) {
	var results types.AnalyzeResults

	// Convert pages to Base64
	base64SourceData := pdfToBase64(pdfData)
	// API request URL
	ocrPostURL := fmt.Sprintf("%s/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=2024-11-30&output=pdf", a.BaseURL)

	resultLocation, apimRequestID, err := a.createPOSTRequest(ocrPostURL, base64SourceData)
	if err != nil {
		return results, fmt.Errorf("failed to initiate document analysis: %w", err)
	} else {
		wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), apimRequestID, "azureocrrequestcreated", "")
	}
	results, err = a.getAnalysisResults(resultLocation, message, apimRequestID)
	if err != nil {
		return results, fmt.Errorf("failed to fetch analysis results: %w", err)
	}
	results, newOCRS3Url, err := a.uploadSearchablePDF(resultLocation, message.CompressedS3FilePath)
	if err == nil {
		wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), apimRequestID, "ocrfileuploadsuccess", newOCRS3Url)
	}
	fmt.Printf("Analysis Results: %v\n", results)
	return results, err

}

func (a *AzureService) uploadSearchablePDF(resultLocation string, s3FilePath string) (types.AnalyzeResults, string, error) {
	var results types.AnalyzeResults
	// Construct PDF retrieval URL
	pdfURL1 := strings.Replace(resultLocation, "?api-version=2024-11-30", "", 1)
	pdfURL := pdfURL1 + "/pdf?api-version=2024-11-30"
	fmt.Printf("\n pdfURL: %s\n", pdfURL)
	// Download the searchable PDF
	pdfReq, _ := http.NewRequest("GET", pdfURL, nil)
	pdfReq.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)
	pdfResp, err := a.Client.Do(pdfReq)
	if err != nil {
		return results, "", err
	}
	defer pdfResp.Body.Close()
	// Check response status
	if pdfResp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(pdfResp.Body)
		return results, "", fmt.Errorf("failed to retrieve PDF: %d %s", pdfResp.StatusCode, string(body))
	}
	pdfBody, err := io.ReadAll(pdfResp.Body)
	if err != nil {
		return results, "", fmt.Errorf("failed to read PDF body: %v", err)
	}
	if len(pdfBody) == 0 {
		return results, "", fmt.Errorf("empty PDF response body")
	}
	fmt.Printf("\n Reached point\n")
	presignedUploadURL, err := s3services.GeneratePresignedUploadURL(s3FilePath)
	if err != nil {
		fmt.Println("Error generating presigned URL:", err)
		return results, "", fmt.Errorf("failed to generate presigned url for upload PDF: %v", err)
	}
	// Upload the compressed PDF back to S3
	err = s3services.UploadUsingPresignedURL(presignedUploadURL, pdfBody)
	if err != nil {
		return results, "", err
	}
	newOCRS3Url := strings.SplitN(presignedUploadURL, "?", 2)[0]
	return results, newOCRS3Url, nil
}

func (a *AzureService) createPOSTRequest(postURL string, base64SourceData string) (string, string, error) {

	fmt.Printf("postURL: %s\n", postURL)
	jsonPayload := fmt.Sprintf(`{"base64Source": "%s"}`, base64SourceData)
	requestBody := bytes.NewBuffer([]byte(jsonPayload))
	req, _ := http.NewRequest(http.MethodPost, postURL, requestBody)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)
	resp, err := a.Client.Do(req)
	fmt.Printf("\nresp: %v\n", resp)
	if err != nil {
		fmt.Printf("client: error making http request: %s\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	// Check for HTTP status
	if resp.StatusCode != http.StatusAccepted {
		body, _ := io.ReadAll(resp.Body)
		return "", "", fmt.Errorf("POST request failed: %d %s", resp.StatusCode, string(body))
	}
	// Extract "Operation-Location" from headers
	resultLocation := resp.Header.Get("Operation-Location")
	fmt.Printf("\nresultLocation: %s\n", resultLocation)
	if resultLocation == "" {
		return "", "", fmt.Errorf("Operation-Location header not found")
	}

	apimRequestID := resp.Header.Get("Apim-Request-Id")
	fmt.Printf("\napimRequestID: %s\n", apimRequestID)

	if apimRequestID == "" {
		return "", "", fmt.Errorf("missing Apim-Request-Id in response header")
	}
	return resultLocation, apimRequestID, nil
}

func (a *AzureService) getAnalysisResults(resultLocation string, message types.QueueMessage, apimRequestID string) (types.AnalyzeResults, error) {
	// Upon successful completion, retrieve the PDF as application/pdf.
	// GET /documentModels/prebuilt-read/analyzeResults/{resultId}/pdf
	// 200 OK
	// Content-Type: application/pdf
	// Poll the GET request until the operation is complete
	var result types.AnalyzeResults
	for {
		time.Sleep(5 * time.Second) // Wait before polling
		getReq, _ := http.NewRequest("GET", resultLocation, nil)
		getReq.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)

		getResponse, err := a.Client.Do(getReq)
		if err != nil {
			return result, err
		}
		defer getResponse.Body.Close()

		// Read response body
		body, _ := io.ReadAll(getResponse.Body)
		if getResponse.StatusCode == http.StatusOK {
			fmt.Println("OCR processing complete")
			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), apimRequestID, "ocrsucceeded", "")
			break
		} else if getResponse.StatusCode == http.StatusAccepted {
			fmt.Println("Processing... Please wait.")
			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), apimRequestID, "ocrjobrunning", "")
			continue
		} else {
			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), apimRequestID, "ocrjobfailed", "")
			return result, fmt.Errorf("GET request failed: %d %s", getResponse.StatusCode, string(body))
		}
	}
	return result, nil
}

func wrapDocReviewerUpdate(documentid int64, ministryrequestid int64, apimRequestID string, status string, ocrFilePath string) bool {
	// ministryrequestid, minreqidconerr := strconv.ParseInt(ministryrequestidrequest, 10, 64)
	// if minreqidconerr != nil {
	// 	fmt.Sprint("Error while converting ministry request ID")
	// }
	docreviewaudit := types.DocReviewAudit{DocumentID: documentid, MinistryRequestID: ministryrequestid,
		Description: fmt.Sprintf(`{apimRequestID:%v}`, apimRequestID), Status: status, OCRFilePath: ocrFilePath}
	returnstate := docreviewerocrservice.PushtoDocReviewer(docreviewaudit)
	return returnstate
}

func CallAzureOCRService(pdfData []byte, message types.QueueMessage) (types.AnalyzeResults, error) {
	// Load environment variables
	subscriptionKey := utils.ViperEnvVariable("azuresubcriptionkey")
	baseURL := utils.ViperEnvVariable("azuredocumentocraiendpoint")
	service := NewAzureService(subscriptionKey, baseURL)
	// Run the function
	result, err := service.performOCR(pdfData, message)
	if err != nil {
		fmt.Println("Error:", err)
	}
	return result, err
}
