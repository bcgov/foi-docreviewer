package models

type OCRAzureMessage struct {
	BCGovCode     string `json:"bcgovcode"`
	RequestNumber string `json:"requestnumber"`
	// Filename          string `json:"filename"`
	MinistryRequestID int `json:"ministryrequestid"`
	//Batch             string `json:"batch"`
	//JobID             int    `json:"jobid"`
	DocumentMasterID int    `json:"documentmasterid"`
	Trigger          string `json:"trigger"`
	//CreatedBy                string     `json:"createdby"`
	//Incompatible             *bool      `json:"incompatible,omitempty"`
	//UserToken *string `json:"usertoken,omitempty"`
	//Attributes               Attributes `json:"attributes"`
	CompressedS3FilePath string `json:"compresseds3filepath,omitempty"`
	DocumentID           int    `json:"documentid"`
}
