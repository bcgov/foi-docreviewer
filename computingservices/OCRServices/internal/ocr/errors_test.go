package ocr

import (
	"errors"
	"strings"
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
	if !errors.Is(Retryable(base), base) {
		t.Fatal("retryable wrapper must expose the cause via errors.Is")
	}
}

// TestClassificationErrorStringsAreSafe asserts that the Error() string of a
// classified error never leaks the raw underlying error text — only the
// bounded safe code is returned, while Unwrap still exposes the cause.
func TestClassificationErrorStringsAreSafe(t *testing.T) {
	rawMsg := "sensitive db connection string: postgres://user:pass@host/db"
	base := errors.New(rawMsg)

	t.Run("permanent does not leak raw error", func(t *testing.T) {
		pErr := Permanent(base)
		if strings.Contains(pErr.Error(), rawMsg) {
			t.Fatalf("permanent error string leaked raw message: %q", pErr.Error())
		}
		if pErr.Error() != "permanent_handler_error" {
			t.Fatalf("expected permanent_handler_error, got %q", pErr.Error())
		}
		if !errors.Is(pErr, base) {
			t.Fatal("errors.Is must still traverse to base via Unwrap")
		}
	})

	t.Run("retryable does not leak raw error", func(t *testing.T) {
		rErr := Retryable(base)
		if strings.Contains(rErr.Error(), rawMsg) {
			t.Fatalf("retryable error string leaked raw message: %q", rErr.Error())
		}
		if rErr.Error() != "retryable_handler_error" {
			t.Fatalf("expected retryable_handler_error, got %q", rErr.Error())
		}
		if !errors.Is(rErr, base) {
			t.Fatal("errors.Is must still traverse to base via Unwrap")
		}
	})
}

// TestNilClassification ensures wrapping nil returns nil (no spurious errors).
func TestNilClassification(t *testing.T) {
	if Permanent(nil) != nil {
		t.Fatal("Permanent(nil) must return nil")
	}
	if Retryable(nil) != nil {
		t.Fatal("Retryable(nil) must return nil")
	}
}
