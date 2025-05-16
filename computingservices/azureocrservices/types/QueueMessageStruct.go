package types

type QueueMessage struct {
	MinistryRequestId    int    `json:"ministryRequestId"`
	RequestNumber        string `json:"requestNumber"`
	MinistryCode         string `json:"ministryCode"`
	DocumentID           int    `json:"documentId"`
	DocumentMasterID     int    `json:"documentMasterId"`
	CompressedS3FilePath string `json:"compressedS3FilePath"`
}
