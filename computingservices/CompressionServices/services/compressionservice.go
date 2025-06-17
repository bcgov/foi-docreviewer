package services

import (
	"fmt"

	"compressionservices/models"
)

func ProcessMessage(message *models.CompressionProducerMessage) {
	// Record cpmpressionjob start
	RecordCompressionJobStart(message)
	// Ensure recovery from any panic during the process
	defer func() {
		if r := recover(); r != nil {
			// Log the panic error and record the job end with failure status
			fmt.Printf("Exception while processing redis message for compression, func ProcessMessage, Error: %v\n", r)
			errMsg := fmt.Sprintf("%v", r)
			RecordCompressionJobEnd("", message, true, errMsg)
		}
	}()
	//fmt.Printf("Just before compression-%v\n", message.S3FilePath)
	s3FilePath, compressedFileSize, extension, isError, errMsg := StartCompression(message)
	errorMessage := ""
	if errMsg != nil {
		errorMessage = errMsg.Error()
	}
	errorMsg := RecordCompressionJobEnd(s3FilePath, message, isError, errorMessage)
	if errMsg == nil && errorMsg == nil {
		message.CompressedS3FilePath = s3FilePath
		// needsOCR := false
		// if message.NeedsOCR != nil {
		// 	needsOCR = *message.NeedsOCR
		// }
		/**Redaction status - isredactionready is set
		only for searchable pdfs. OCR'd documents status should be
		updated after Azure AI OCR is finished*/
		// if !needsOCR {
		// 	UpdateRedactionStatus(message)
		// }
		updateError := UpdateDocumentDetails(message, compressedFileSize, s3FilePath)
		if updateError != nil {
			fmt.Printf("Failed to update document details: %v\n", updateError)
		}
		/**Commenting logic check for needs_ocr field - if needsOCR*/
		fmt.Printf("extension: %v", extension)
		if extension == ".pdf" {
			fmt.Printf("\nStarting OCR!!")
			ocrjobid, err := RecordOCRJobStart(message)
			if err != nil {
				fmt.Printf("Failed to record OCR job: %v\n", err)
			}
			message.JobID = ocrjobid
			id, streamerr := NewOCRProducerService().ProduceOCREvent(message, ocrjobid)
			if streamerr != nil {
				fmt.Printf("Failed to push OCR job to stream: %v\n", streamerr)
			}
			print("\nPushed to OCR Stream-", id)
		} else {
			UpdateRedactionStatus(message)
		}
	}
}
