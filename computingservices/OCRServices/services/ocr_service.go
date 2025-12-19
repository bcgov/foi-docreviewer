package services

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"

	"ocrservices/models"
	"ocrservices/utils"
)

var ACTIVEMQ_URL string = utils.ViperEnvVariable("ACTIVEMQ_URL")
var ACTIVEMQ_USERNAME string = utils.ViperEnvVariable("ACTIVEMQ_USERNAME")
var ACTIVEMQ_PASSWORD string = utils.ViperEnvVariable("ACTIVEMQ_PASSWORD")
var ACTIVEMQ_DESTINATION string = utils.ViperEnvVariableWithDefault("ACTIVEMQ_DESTINATION", "foidococr")

func ProcessMessage(message *models.OCRProducerMessage) {
	// Record compressionjob start
	RecordJobStart(message)
	// Ensure recovery from any panic during the process
	defer func() {
		if r := recover(); r != nil {
			// Log the panic error and record the job end with failure status
			fmt.Printf("Exception while processing redis message for OCR, func ProcessMessage, Error: %v\n", r)
			errMsg := fmt.Sprintf("%v", r)
			RecordJobEnd(message, true, errMsg)
		}
	}()
	ocrActiveMQMsg := models.OCRAzureMessage{
		BCGovCode:            message.BCGovCode,
		RequestNumber:        message.RequestNumber,
		MinistryRequestID:    message.MinistryRequestID,
		DocumentMasterID:     message.DocumentMasterID,
		Trigger:              message.Trigger,
		S3FilePath:           message.S3FilePath,
		CompressedS3FilePath: message.CompressedS3FilePath,
		DocumentID:           message.DocumentID,
	}
	response, err := pushDocsToActiveMQ(&ocrActiveMQMsg)
	fmt.Printf("Response from activemq: %v\n", response)
	isError := false
	errMsg := ""
	if err != nil {
		fmt.Printf("Failed to push to activemq: %v\n", err)
		isError = true
		errMsg = fmt.Sprintf("%v", err)
		RecordJobEnd(message, true, errMsg)
	}
	if response != nil {
		RecordJobEnd(message, isError, errMsg)
	}
}

func pushDocsToActiveMQ(message *models.OCRAzureMessage) (*http.Response, error) {

	url := ACTIVEMQ_URL
	username := ACTIVEMQ_USERNAME
	password := ACTIVEMQ_PASSWORD
	params := "?destination=queue://" + ACTIVEMQ_DESTINATION
	//fmt.Println("\nACTIVEMQ_URL:", url)
	if message != nil {
		jsonBytes, err := json.Marshal(message)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal message: %v", err)
		}
		req, err := http.NewRequest("POST", url+params, bytes.NewBuffer(jsonBytes))
		if err != nil {
			return nil, fmt.Errorf("failed to create request: %v", err)
		}
		req.SetBasicAuth(username, password)
		req.Header.Set("Content-Type", "application/json")
		client := &http.Client{}
		resp, err := client.Do(req)
		if err != nil {
			fmt.Printf("Activemq request failed: %v\n", err)
			return nil, err
		}
		defer resp.Body.Close()
		body, _ := io.ReadAll(resp.Body)
		if resp.StatusCode == 200 {
			fmt.Println("Success:", string(body))
		} else {
			fmt.Printf("Error: %d, %s\n", resp.StatusCode, string(body))
		}
		return resp, nil
	}
	return nil, nil
}
