package contracts

import messaging "github.com/bcgov/foi-messaging-go"

const (
	OCREventType     = "document.ocr.requested"
	OCRSchemaVersion = "1.0.0"
	OCRTopic         = "ocr"
)

// OCRRequested is the typed event OCRServices consumes. topic selects the
// Redis stream (via foi-messaging-go's StreamPrefix:topic convention),
// letting deployments split traffic (e.g. by file size) across separate
// consumer processes without changing the event type or schema version.
func OCRRequested(topic string) messaging.EventDef {
	return messaging.EventDef{
		Topic:   topic,
		Type:    OCREventType,
		Version: OCRSchemaVersion,
	}
}
