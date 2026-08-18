package contracts

import messaging "github.com/bcgov/foi-messaging-go"

const (
	CompressionEventType     = "document.compression.requested"
	CompressionSchemaVersion = "1.0.0"
)

func CompressionRequested(topic string) messaging.EventDef {
	return messaging.EventDef{
		Topic:   topic,
		Type:    CompressionEventType,
		Version: CompressionSchemaVersion,
	}
}
