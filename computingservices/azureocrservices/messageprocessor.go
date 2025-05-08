package main

import (
	"azureocrservice/azureservices"
	"azureocrservice/httpservices"
	"azureocrservice/s3services"
	"fmt"
	"log"
	"net/url"
	"strings"
	"time"
)

type AzureExtract struct {
	status        string
	analyzeResult string
}

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
		var jsonStrbytes []byte = getBytesfromDocumentPath(message.S3Uri)
		analysisResults, _analyzeerr := azureservices.CallAzureOCRService(jsonStrbytes)
		if _analyzeerr == nil && analysisResults.Status == "succeeded" {

			// searchdocumentpagelines := []types.SOLRSearchDocument{}
			// //pUSH to solr.
			// for _, page := range analysisResults.AnalyzeResult.Pages {
			// 	for _, line := range page.Lines {
			// 		receviedDate, timeparseerror := time.Parse(time.RFC3339, request.ReceivedDate)
			// 		if timeparseerror != nil {
			// 			fmt.Println("Error parsing custom date-time:", timeparseerror)
			// 		}
			// 		newUUID := uuid.New()
			// 		_solrsearchdocuemnt := types.SOLRSearchDocument{
			// 			Foisolrid:              newUUID.String(),
			// 			FoiDocumentID:          strconv.Itoa(int(document.DocumentID)),
			// 			FoiRequestNumber:       request.RequestNumber,
			// 			FoiMinistryRequestID:   request.MinistryRequestID,
			// 			FoiMinistryCode:        request.MinistryCode,
			// 			FoiDocumentFileName:    document.DocumentName,
			// 			FoiDocumentPageNumber:  page.PageNumber,
			// 			FoiDocumentSentence:    line.Content,
			// 			FoiRequestMiscInfo:     request.RequestMiscInfo,
			// 			FoiRequestReceivedDate: receviedDate,
			// 			FoiDocumentURL:         document.DocumentS3URL,
			// 			FoiRequestType:         request.RequestType,
			// 		}
			// 		searchdocumentpagelines = append(searchdocumentpagelines, _solrsearchdocuemnt)
			// 		fmt.Println(_solrsearchdocuemnt.FoiDocumentFileName)
			// 	}

			// }

			//solrsearchservices.PushtoSolr(searchdocumentpagelines)

		}

		// Get the path after the hostname
		fmt.Printf("################-------------------------------####################")
	}
	end := time.Now()
	fmt.Println("End Time :" + end.String())
	total := end.Sub(start)
	fmt.Println("Total time:" + total.String())
}

func getBytesfromDocumentPath(documenturlpath string) []byte {
	//path := strings.TrimPrefix(documenturlpath, "/")
	//bucketName, relativePath, found := strings.Cut(path, "/")
	parsedURL, err := url.Parse(documenturlpath)
	if err != nil {
		fmt.Println("Error in parsing URL")
		return nil
	}
	relativePath := parsedURL.Path
	relativePath = strings.TrimPrefix(relativePath, "/")
	bucketName, relativePath, found := strings.Cut(relativePath, "/")
	if !found {
		fmt.Println("Invalid URL format")
		return nil
	}
	fmt.Printf("Bucket: %s, Key: %s\n", bucketName, relativePath)
	var s3url = s3services.GetFilefroms3(relativePath, bucketName)
	jsonStr := `{
			"urlSource": "` + s3url + `"
		}`
	var jsonStrbytes = []byte(jsonStr)

	return jsonStrbytes
}
