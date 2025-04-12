package models

type CompressionProducerMessage struct {
	S3FilePath            string `json:"s3filepath"`
	RequestNumber         string `json:"requestnumber"`
	Filename              string `json:"filename"`
	MinistryRequestID     string `json:"ministryrequestid"`
	Batch                 string `json:"batch"`
	JobID                 int    `json:"jobid"`
	DocumentMasterID      string `json:"documentmasterid"`
	InputDocumentMasterID int    `json:"inputdocumentmasterid,omitempty"`
	Trigger               string `json:"trigger"`
	CreatedBy             string `json:"createdby"`
	//Incompatible          *bool   `json:"incompatible,omitempty"`
	UserToken *string `json:"usertoken,omitempty"`
}
