package models

type OCRProducerMessage struct {
	BCGovCode            string  `json:"bcgovcode"`
	S3FilePath           string  `json:"s3filepath"`
	RequestNumber        string  `json:"requestnumber"`
	Filename             string  `json:"filename"`
	MinistryRequestID    int     `json:"ministryrequestid"`
	Batch                string  `json:"batch"`
	JobID                int     `json:"jobid"`
	DocumentMasterID     int     `json:"documentmasterid"`
	Trigger              string  `json:"trigger"`
	CreatedBy            string  `json:"createdby"`
	Incompatible         *bool   `json:"incompatible,omitempty"`
	UserToken            *string `json:"usertoken,omitempty"`
	CompressedS3FilePath string  `json:"compresseds3filepath,omitempty"`
	DocumentID           int     `json:"documentid"`
}

type Division struct {
	DivisionID int `json:"divisionid"`
}
