package ocr

import (
	"errors"
	"testing"
)

func TestClassification(t *testing.T) {
	base := errors.New("boom")
	if !IsPermanent(Permanent(base)) {
		t.Fatal("Permanent should be permanent")
	}
	if IsPermanent(Retryable(base)) {
		t.Fatal("Retryable should not be permanent")
	}
	if !errors.Is(Permanent(base), base) {
		t.Fatal("wrapper must expose the cause via errors.Is")
	}
}
