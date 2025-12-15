package types

type QueueMessage struct {
	MinistryRequestId    int    `json:"ministryRequestId"`
	RequestNumber        string `json:"requestNumber"`
	MinistryCode         string `json:"ministryCode"`
	DocumentID           int    `json:"documentId"`
	DocumentMasterID     int    `json:"documentMasterId"`
	S3FilePath           string `json:"S3FilePath"`
	CompressedS3FilePath string `json:"compressedS3FilePath"`
}
