package azureservices

import (
	"azureocrservice/docreviewerocrservice"
	"azureocrservice/s3services"
	"azureocrservice/types"
	"azureocrservice/utils"
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
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
func (a *AzureService) performOCR(pdfData []byte, message types.QueueMessage) (string, error) {
	var result string

	// Convert pages to Base64
	base64SourceData := pdfToBase64(pdfData)
	// API request URL
	ocrPostURL := fmt.Sprintf("%s/documentintelligence/documentModels/prebuilt-read:analyze?_overload=analyzeDocument&api-version=2024-11-30&output=pdf", a.BaseURL)
	resultLocation, apimRequestID, err := a.createPOSTRequest(ocrPostURL, base64SourceData)
	if err != nil {
		return result, fmt.Errorf("failed to initiate document analysis: %w", err)
	} else {
		wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), int64(message.DocumentMasterID), apimRequestID, "azureocrrequestcreated", "")
	}
	result, err = a.getAnalysisResults(resultLocation, message, apimRequestID)
	if err != nil {
		return result, fmt.Errorf("failed to fetch analysis results: %w", err)
	}
	results, newOCRS3Url, err := a.uploadSearchablePDF(resultLocation, message.CompressedS3FilePath)
	fmt.Printf("newOCRS3Url: %s", newOCRS3Url)
	if err == nil {
		wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId), int64(message.DocumentMasterID), apimRequestID, "ocrfileuploadsuccess", newOCRS3Url)
	}
	fmt.Printf("Analysis Results: %v\n", results)
	return result, err

}

func (a *AzureService) uploadSearchablePDF(resultLocation string, s3FilePath string) (string, string, error) {
	// Construct PDF retrieval URL
	pdfURL1 := strings.Replace(resultLocation, "?api-version=2024-11-30", "", 1)
	pdfURL := pdfURL1 + "/pdf?api-version=2024-11-30"
	//fmt.Printf("\n pdfURL: %s\n", pdfURL)
	// Download the searchable PDF
	pdfReq, _ := http.NewRequest("GET", pdfURL, nil)
	pdfReq.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)
	pdfResp, err := a.Client.Do(pdfReq)
	if err != nil {
		return "", "", err
	}
	defer pdfResp.Body.Close()
	// Check response status
	if pdfResp.StatusCode != http.StatusOK {
		io.Copy(io.Discard, pdfResp.Body) // Discard all content
		pdfResp.Body.Close()              // Then close

		//body, _ := io.ReadAll(pdfResp.Body)
		return "", "", fmt.Errorf("failed to retrieve PDF: %v", pdfResp.StatusCode)
	}
	pdfBody, err := io.ReadAll(pdfResp.Body)
	if err != nil {
		return "", "", fmt.Errorf("failed to read PDF body: %v", err)
	}
	// if len(pdfBody) == 0 {
	// 	return results, "", fmt.Errorf("empty PDF response body")
	// }
	if len(pdfBody) == 0 || !bytes.HasPrefix(pdfBody, []byte("%PDF")) {
		return "", "", fmt.Errorf("unexpected PDF content (possibly truncated or not a PDF)")
	}
	//fmt.Printf("\n Reached point\n")
	presignedUploadURL, err := s3services.GeneratePresignedUploadURL(s3FilePath)
	if err != nil {
		fmt.Println("Error generating presigned URL:", err)
		return "", "", fmt.Errorf("failed to generate presigned url for upload PDF: %v", err)
	}
	// Upload the compressed PDF back to S3
	err = s3services.UploadUsingPresignedURL(presignedUploadURL, pdfBody)
	if err != nil {
		return "", "", err
	}
	newOCRS3Url := strings.SplitN(presignedUploadURL, "?", 2)[0]
	return pdfResp.Status, newOCRS3Url, nil
}

func (a *AzureService) createPOSTRequest(postURL string, base64SourceData string) (string, string, error) {

	payload := map[string]string{"base64Source": base64SourceData}
	jsonBytes, err := json.Marshal(payload)
	if err != nil {
		return "", "", fmt.Errorf("failed to marshal JSON payload: %w", err)
	}
	// Create HTTP request
	req, err := http.NewRequest(http.MethodPost, postURL, bytes.NewBuffer(jsonBytes))
	if err != nil {
		return "", "", fmt.Errorf("failed to create HTTP request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)
	// Perform the request
	resp, err := a.Client.Do(req)
	if err != nil {
		return "", "", fmt.Errorf("HTTP request failed: %w", err)
	}
	defer resp.Body.Close()
	// Check HTTP response status
	if resp.StatusCode != http.StatusAccepted {
		body, _ := io.ReadAll(resp.Body) // Read body for debugging purposes
		return "", "", fmt.Errorf("unexpected status code %d: %s", resp.StatusCode, string(body))
	}
	// Extract required headers
	resultLocation := resp.Header.Get("Operation-Location")
	if resultLocation == "" {
		return "", "", errors.New("missing 'Operation-Location' header in response")
	}
	apimRequestID := resp.Header.Get("Apim-Request-Id")
	if apimRequestID == "" {
		return "", "", errors.New("missing 'Apim-Request-Id' header in response")
	}
	return resultLocation, apimRequestID, nil
}

func (a *AzureService) getAnalysisResults(resultLocation string, message types.QueueMessage, apimRequestID string) (string, error) {
	// Upon successful completion, retrieve the PDF as application/pdf.
	// GET /documentModels/prebuilt-read/analyzeResults/{resultId}/pdf
	// 200 OK
	// Content-Type: application/pdf
	// Poll the GET request until the operation is complete
	var result types.AnalyzeResults
	for {
		time.Sleep(5 * time.Second) // Wait before polling
		getReq, getErr := http.NewRequest("GET", resultLocation, nil)
		if getErr != nil {
			return "", fmt.Errorf("failed to create HTTP GET request: %w", getErr)
		}
		getReq.Header.Set("Ocp-Apim-Subscription-Key", a.SubscriptionKey)
		getReq.Header.Set("Accept", "application/json")
		getResponse, getRespErr := a.Client.Do(getReq)
		if getRespErr != nil {
			return "", getRespErr
		}
		defer getResponse.Body.Close()

		// Read response body
		body, readErr := io.ReadAll(getResponse.Body)
		if readErr != nil {
			return "", fmt.Errorf("failed to read response body: %v", readErr)
		}

		var statusResp struct {
			Status string `json:"status"`
		}
		if err := json.Unmarshal(body, &statusResp); err != nil {
			fmt.Printf("\nocr job failed: %sv\n", err)

			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId),
				int64(message.DocumentMasterID), apimRequestID, "ocrjobfailed", "")
			return "", fmt.Errorf("failed to parse status: %v", err)
		}
		switch statusResp.Status {
		case "notStarted", "running":
			fmt.Printf("Processing document : %v Please wait.\n", message.DocumentID)
			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId),
				int64(message.DocumentMasterID), apimRequestID, "ocrjobrunning", "")
			continue

		case "succeeded":
			fmt.Println("OCR processing completed.")

			if err := json.Unmarshal(body, &result); err != nil {
				wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId),
					int64(message.DocumentMasterID), apimRequestID, "ocrjobfailed", "")
				return getResponse.Status, fmt.Errorf("failed to unmarshal analysis results: %v", err)
			}

			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId),
				int64(message.DocumentMasterID), apimRequestID, "ocrjobsucceeded", "")
			return getResponse.Status, nil

		default:
			wrapDocReviewerUpdate(int64(message.DocumentID), int64(message.MinistryRequestId),
				int64(message.DocumentMasterID), apimRequestID, "ocrjobfailed", "")
			return getResponse.Status, fmt.Errorf("OCR job failed or unknown status: %s", statusResp.Status)
		}
	}
}

func wrapDocReviewerUpdate(documentid int64, ministryrequestid int64, documentmasterid int64, apimRequestID string, status string, ocrFilePath string) bool {
	docreviewaudit := types.DocReviewAudit{DocumentID: documentid, MinistryRequestID: ministryrequestid, DocumentMasterID: documentmasterid,
		Description: fmt.Sprintf(`{apimRequestID:%v}`, apimRequestID), Status: status, OCRFilePath: ocrFilePath}
	returnstate := docreviewerocrservice.PushtoDocReviewer(docreviewaudit)
	return returnstate
}

func CallAzureOCRService(pdfData []byte, message types.QueueMessage) (string, error) {
	// Load environment variables
	subscriptionKey := utils.ViperEnvVariable("azuresubcriptionkey")
	baseURL := utils.ViperEnvVariable("azuredocumentocraiendpoint")
	service := NewAzureService(subscriptionKey, baseURL)
	// Run the function
	result, err := service.performOCR(pdfData, message)
	if err != nil {
		fmt.Println("Error while performing OCR:", err)
	}
	return result, err
}
