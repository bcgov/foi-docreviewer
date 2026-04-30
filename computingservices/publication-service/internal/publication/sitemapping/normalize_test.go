package sitemapping

import (
	"encoding/json"
	"testing"

	"publication-service/internal/events"
	pub "publication-service/internal/publish"
)

func goodSitemapEnvelope(kind string) *events.Envelope {
	payload, _ := json.Marshal(map[string]any{
		"tenant_id":              "a7d9b2f1-4c3e-4e8b-9a21-1c2e8f7b9d10",
		"publication_id":         "HTH-001",
		"public_url":             "https://public.example/foi-published/out/a7d9b2f1/HTH-001.html",
		"last_modified":          "2025-04-01",
		"publication_result_ref": "ref-123",
		"kind":                   kind,
	})
	return &events.Envelope{
		EventID:       "evt-sm-001",
		EventType:     events.TypePublicationSitemappingRequested,
		SchemaVersion: events.SchemaVersionV1,
		CorrelationID: "corr-sm-001",
		Source:        "test",
		Payload:       payload,
	}
}

func TestNormalize_OpenInfoSitemap(t *testing.T) {
	env := goodSitemapEnvelope("openinfo")
	req, err := Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if req.Kind != pub.KindOpenInfoSitemap {
		t.Errorf("Kind = %q, want %q", req.Kind, pub.KindOpenInfoSitemap)
	}
	if req.PublicationID != "HTH-001" {
		t.Errorf("PublicationID = %q", req.PublicationID)
	}
}

func TestNormalize_PDSitemap(t *testing.T) {
	env := goodSitemapEnvelope("proactivedisclosure")
	req, err := Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if req.Kind != pub.KindProactiveDisclosureSitemap {
		t.Errorf("Kind = %q, want %q", req.Kind, pub.KindProactiveDisclosureSitemap)
	}
}

func TestNormalize_RejectsBadDate(t *testing.T) {
	env := goodSitemapEnvelope("openinfo")
	env.Payload = json.RawMessage(`{
		"tenant_id": "a7d9b2f1-4c3e-4e8b-9a21-1c2e8f7b9d10",
		"publication_id": "X",
		"public_url": "https://x",
		"last_modified": "not-a-date",
		"publication_result_ref": "ref",
		"kind": "openinfo"
	}`)
	_, err := Normalize(env)
	if err == nil {
		t.Fatal("expected error for bad date")
	}
}
