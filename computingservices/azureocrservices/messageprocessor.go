package main

import (
	"azureocrservice/azureservices"
	"azureocrservice/httpservices"
	"azureocrservice/s3services"
	"azureocrservice/utils"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strconv"
	"time"
)

func main() {

	start := time.Now()
	fmt.Println("\nStart Time :" + start.String())

	y, m, d := start.Date()
	filedate := strconv.Itoa(y) + "-" + strconv.Itoa(int(m)) + "-" + strconv.Itoa(d)
	logfilepath := utils.ViperEnvVariable("logfilepath")
	file, err := os.OpenFile(logfilepath+filedate+"dococrlog.txt", os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0644)

	if err != nil {
		fmt.Println("Error opening file:", err)
		return
	}
	defer file.Close()
	// Redirect stdout to the file.
	os.Stdout = file

	dequeuedmessages, err := httpservices.ProcessMessage()
	if err != nil {
		log.Fatalf("Error fetching messages: %v", err)
	}
	for _, message := range dequeuedmessages {
		fmt.Printf("Received message: %+v\n", message)

		var s3Uribytes []byte = getBytesfromDocumentPath(message.CompressedS3FilePath)
		_, _analyzeerr := azureservices.CallAzureOCRService(s3Uribytes, message)
		//&& analysisResults.Status == "succeeded"
		if _analyzeerr == nil {
			fmt.Println("OCR finished successfully!")
		}
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
	pdfData, err := DownloadFile(s3url)
	if err != nil {
		fmt.Println("Error downloading PDF:", err)
		return nil
	}
	return pdfData
}
