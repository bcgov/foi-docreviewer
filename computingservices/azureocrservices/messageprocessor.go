package main

import (
	"azureocrservice/azureservices"
	"azureocrservice/httpservices"
	"azureocrservice/s3services"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"
)

func main() {

	start := time.Now()
	fmt.Println("Start Time :" + start.String())
	dequeuedmessages, err := httpservices.ProcessMessage()
	if err != nil {
		log.Fatalf("Error fetching messages: %v", err)
	}
	// Print each message
	for _, message := range dequeuedmessages {
		fmt.Printf("Received message: %+v\n", message)
		//var jsonStrbytes []byte =
		//var message types.QueueMessage
		fmt.Printf("\nReceived URL: %+v\n", message.CompressedS3FilePath)
		var s3Uribytes []byte = getBytesfromDocumentPath(message.CompressedS3FilePath)
		analysisResults, _analyzeerr := azureservices.CallAzureOCRService(s3Uribytes, message)
		if _analyzeerr == nil && analysisResults.Status == "succeeded" {
			fmt.Println("OCR finished successfully!")
		}
		fmt.Printf("################-------------------------------####################")
	}
	end := time.Now()
	fmt.Println("End Time :" + end.String())
	total := end.Sub(start)
	fmt.Println("Total time:" + total.String())
}

func DownloadFile(url string) ([]byte, error) {
	// Send an HTTP GET request to the URL
	resp, err := http.Get(url)
	if err != nil {
		return nil, fmt.Errorf("error downloading file: %v", err)
	}
	defer resp.Body.Close()
	// Read the file data into a byte slice
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading downloaded file: %v", err)
	}
	return data, nil
}

func getBytesfromDocumentPath(documenturlpath string) []byte {
	s3url, err := s3services.GenerateDownloadPresignedURL(documenturlpath)
	if err != nil {
		log.Fatalf("Error generating presigned URL: %v", err)
		return nil
	}
	fmt.Println("s3url:", s3url)
	pdfData, err := DownloadFile(s3url)
	if err != nil {
		fmt.Println("Error downloading PDF:", err)
		return nil
	}
	return pdfData
}
