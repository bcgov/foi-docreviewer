package types

type OCRJob struct {
	OCRJobId          int    `json:"ocrjobid"`
	Version           int    `json:"version"`
	DocumentId        int    `json:"documentid"`
	MinistryRequestID int    `json:"ministryrequestid"`
	Status            string `json:"status"`
	OCRFilePath       string `json:"ocrfilepath,omitempty"`
	DocumentMasterID  int    `json:"documentmasterid"`
	Message           string `json:"message"`
}
