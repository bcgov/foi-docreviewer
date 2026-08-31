package contracts

import "testing"

func TestOCRRequestedDefinition(t *testing.T) {
	def := OCRRequested()
	if def.Topic != "ocr" || def.Type != "document.ocr.requested" || def.Version != "1.0.0" {
		t.Fatalf("unexpected OCR event def: %+v", def)
	}
}
