package contracts

import messaging "github.com/bcgov/foi-messaging-go"

const (
	OCREventType     = "document.ocr.requested"
	OCRSchemaVersion = "1.0.0"
	OCRTopic         = "ocr"
)

// OCRRequested is the typed event OCRServices consumes.
func OCRRequested() messaging.EventDef {
	return messaging.EventDef{
		Topic:   OCRTopic,
		Type:    OCREventType,
		Version: OCRSchemaVersion,
	}
}
