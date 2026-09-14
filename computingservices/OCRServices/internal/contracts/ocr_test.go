package contracts

import "testing"

func TestOCRRequestedDefinition(t *testing.T) {
	def := OCRRequested(OCRTopic)
	if def.Topic != "ocr" || def.Type != "document.ocr.requested" || def.Version != "1.0.0" {
		t.Fatalf("unexpected OCR event def: %+v", def)
	}
}

func TestOCRRequestedCustomTopic(t *testing.T) {
	def := OCRRequested("ocr-large")
	if def.Topic != "ocr-large" || def.Type != "document.ocr.requested" || def.Version != "1.0.0" {
		t.Fatalf("unexpected OCR event def: %+v", def)
	}
}
