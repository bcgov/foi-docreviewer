package types

type DocReviewAudit struct {
	OCRJobId          int    `json:"ocrjobid"`
	Version           int    `json:"version"`
	DocumentID        int64  `json:"documentid"`
	MinistryRequestID int64  `json:"ministryrequestid"`
	DocumentMasterID  int64  `json:"documentmasterid"`
	Status            string `json:"status"`
	Description       string `json:"message"`
	OCRFilePath       string `json:"ocrfilepath,omitempty"`
}
