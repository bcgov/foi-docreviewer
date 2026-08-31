package contracts

import messaging "github.com/bcgov/foi-messaging-go"

const (
	OCREventType     = "document.ocr.requested"
	OCRSchemaVersion = "1.0.0"
	OCRTopic         = "ocr"
)

// OCRRequested is the typed event CompressionServices publishes for OCR work.
func OCRRequested() messaging.EventDef {
	return messaging.EventDef{
		Topic:   OCRTopic,
		Type:    OCREventType,
		Version: OCRSchemaVersion,
	}
}

// OCREventPayload is the canonical payload OCRServices consumes. Field json
// tags MUST stay identical to OCRServices' OCRProducerMessage.
type OCREventPayload struct {
	BCGovCode            string `json:"bcgovcode"`
	S3FilePath           string `json:"s3filepath"`
	RequestNumber        string `json:"requestnumber"`
	Filename             string `json:"filename"`
	MinistryRequestID    int    `json:"ministryrequestid"`
	Batch                string `json:"batch"`
	JobID                int    `json:"jobid"`
	DocumentMasterID     int    `json:"documentmasterid"`
	Trigger              string `json:"trigger"`
	CreatedBy            string `json:"createdby"`
	CompressedS3FilePath string `json:"compresseds3filepath,omitempty"`
	DocumentID           int     `json:"documentid"`
	Incompatible         *bool   `json:"incompatible,omitempty"`
	UserToken            *string `json:"usertoken,omitempty"`
}
