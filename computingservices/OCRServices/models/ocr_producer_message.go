package models

type OCRProducerMessage struct {
	BCGovCode         string `json:"bcgovcode"`
	S3FilePath        string `json:"s3filepath"`
	RequestNumber     string `json:"requestnumber"`
	Filename          string `json:"filename"`
	MinistryRequestID int    `json:"ministryrequestid"`
	Batch             string `json:"batch"`
	JobID             int    `json:"jobid"`
	DocumentMasterID  int    `json:"documentmasterid"`
	//InputDocumentMasterID int    `json:"inputdocumentmasterid,omitempty"`
	Trigger                  string     `json:"trigger"`
	CreatedBy                string     `json:"createdby"`
	Incompatible             *bool      `json:"incompatible,omitempty"`
	UserToken                *string    `json:"usertoken,omitempty"`
	Attributes               Attributes `json:"attributes"`
	OutputDocumentMasterID   *int       `json:"outputdocumentmasterid,omitempty"`
	OriginalDocumentMasterID *int       `json:"originaldocumentmasterid,omitempty"`
	CompressedS3FilePath     string     `json:"compresseds3filepath,omitempty"`
	DocumentID               int        `json:"documentid"`
	NeedsOCR                 *bool      `json:"needsocr"`
}

type Division struct {
	DivisionID int `json:"divisionid"`
}

type Attributes struct {
	FileSize           int            `json:"filesize"`
	PersonalAttributes map[string]any `json:"personalattributes"` // assuming it's a flexible structure
	LastModified       string         `json:"lastmodified"`
	Divisions          []Division     `json:"divisions"`
	Batch              string         `json:"batch"`
	Extension          string         `json:"extension"`
	Incompatible       bool           `json:"incompatible"`
	CompressedSize     *int           `json:"compressedsize,omitempty"` // optional field
	IsAttachment       bool           `json:"isattachment,omitempty"`
	ConvertedFileSize  int            `json:"convertedfilesize,omitempty"`
	RootParentFilePath string         `json:"rootparentfilepath,omitempty"`
}
