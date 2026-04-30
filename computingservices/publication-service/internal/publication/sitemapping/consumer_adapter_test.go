package sitemapping

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"publication-service/internal/events"
	pub "publication-service/internal/publish"
	"publication-service/internal/sitemapping"
)

type fakeWriter struct {
	result sitemapping.Result
	err    error
}

func (f *fakeWriter) Handle(_ context.Context, _ sitemapping.Request) (sitemapping.Result, error) {
	return f.result, f.err
}

func TestConsumerAdapter_CompletionEventType(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeWriter{
		result: sitemapping.Result{TenantID: "t1", PublicationID: "P1", Kind: pub.KindOpenInfoSitemap},
	})
	env := goodSitemapEnvelope("openinfo")
	env.CorrelationID = "corr-123"

	_, handler, buildCompletion, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if err := handler(context.Background()); err != nil {
		t.Fatalf("handler: %v", err)
	}

	_, completionBytes, err := buildCompletion()
	if err != nil {
		t.Fatalf("buildCompletion: %v", err)
	}
	var completion events.Envelope
	if err := json.Unmarshal(completionBytes, &completion); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if completion.EventType != events.TypePublicationSitemappingCompleted {
		t.Errorf("EventType = %q, want %q", completion.EventType, events.TypePublicationSitemappingCompleted)
	}
	if completion.Source != "publication.sitemapping.service" {
		t.Errorf("Source = %q, want %q", completion.Source, "publication.sitemapping.service")
	}
	if completion.CorrelationID != "corr-123" {
		t.Errorf("CorrelationID = %q", completion.CorrelationID)
	}
	var payload map[string]any
	if err := json.Unmarshal(completion.Payload, &payload); err != nil {
		t.Fatalf("unmarshal payload: %v", err)
	}
	if payload["kind"] != "openinfo" {
		t.Errorf("kind = %v, want openinfo", payload["kind"])
	}
}

func TestConsumerAdapter_KindInClaimInfo(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeWriter{})

	env := goodSitemapEnvelope("openinfo")
	info, _, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize OI: %v", err)
	}
	if info.Kind != pub.KindOpenInfoSitemap {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindOpenInfoSitemap)
	}

	env = goodSitemapEnvelope("proactivedisclosure")
	info, _, _, err = adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize PD: %v", err)
	}
	if info.Kind != pub.KindProactiveDisclosureSitemap {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindProactiveDisclosureSitemap)
	}
}

func TestConsumerAdapter_HandlerPropagatesError(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeWriter{err: errors.New("boom")})
	env := goodSitemapEnvelope("openinfo")
	_, handler, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if err := handler(context.Background()); err == nil {
		t.Fatal("expected error")
	}
}
