package docreviewerocrservice

import (
	"azureocrservice/types"
	"azureocrservice/utils"
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

func PushtoDocReviewer(docreviewAudit types.DocReviewAudit) bool {

	// Convert the struct to JSON
	jsonData, err := json.Marshal(docreviewAudit)
	fmt.Println("DocReviwer Audit Data starts here")
	fmt.Println("JSONDATA:", string(jsonData))
	//fmt.Println("DocReviwer Audit ends here")
	if err != nil {
		log.Fatal("Error marshaling JSON:", err)
	}
	url := fmt.Sprintf("%v/api/documentocrjob", utils.ViperEnvVariable("docreviewerocrapiendpoint"))
	// Create a POST request with JSON data
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Fatal("Error creating request:", err)
	}
	// Set the appropriate headers for JSON content
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-FOI-OCR-Secret", utils.ViperEnvVariable("docreviewerocrapisecret"))

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Fatal("Error sending request:", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusCreated || resp.StatusCode == http.StatusOK {
		fmt.Println("Successfully posted to Doc Reviewer audit api")
		return true
	} else {
		fmt.Printf("Failed to post to Reviewer. Status: %s\n", resp.Status)
		return false
	}
}
