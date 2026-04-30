package unpublish

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"publication-service/internal/events"
	pub "publication-service/internal/publish"
	shared "publication-service/internal/unpublish"
)

type fakeService struct {
	result shared.Result
	err    error
}

func (f *fakeService) Handle(_ context.Context, _ shared.Request) (shared.Result, error) {
	return f.result, f.err
}

func TestConsumerAdapter_CompletionEventType(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeService{
		result: shared.Result{TenantID: "tenant-1", PublicationID: "EDU-2024-12345"},
	})
	env := goodUnpublishEnvelope("openinfo")
	env.CorrelationID = "corr-99"

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
	if completion.EventType != events.TypePublicationUnpublishCompleted {
		t.Errorf("EventType = %q, want %q", completion.EventType, events.TypePublicationUnpublishCompleted)
	}
	if completion.Source != "publication.unpublish.service" {
		t.Errorf("Source = %q, want %q", completion.Source, "publication.unpublish.service")
	}
	if completion.CorrelationID != "corr-99" {
		t.Errorf("CorrelationID = %q", completion.CorrelationID)
	}
}

func TestConsumerAdapter_KindInClaimInfo(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeService{})

	env := goodUnpublishEnvelope("openinfo")
	info, _, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize OI: %v", err)
	}
	if info.Kind != pub.KindOpenInfoUnpublish {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindOpenInfoUnpublish)
	}

	env = goodUnpublishEnvelope("proactivedisclosure")
	info, _, _, err = adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize PD: %v", err)
	}
	if info.Kind != pub.KindProactiveDisclosureUnpublish {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindProactiveDisclosureUnpublish)
	}
}

func TestConsumerAdapter_HandlerPropagatesError(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeService{err: errors.New("boom")})
	env := goodUnpublishEnvelope("openinfo")
	_, handler, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if err := handler(context.Background()); err == nil {
		t.Fatal("expected error")
	}
}

func TestConsumerAdapter_CompletionPayloadFields(t *testing.T) {
	adapter := NewNormalizerAdapter(&fakeService{
		result: shared.Result{
			TenantID:               "tenant-1",
			PublicationID:          "EDU-2024-12345",
			PublicRepositoryBucket: "public-bucket",
			PublicRepositoryPrefix: "openinfo/EDU-2024-12345/",
			ObjectsDeleted:         5,
			SitemapIndexKey:        "sitemap/index.xml",
			SitemapPageKey:         "sitemap/page-1.xml",
			SitemapResult:          "removed",
		},
	})
	env := goodUnpublishEnvelope("openinfo")

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
	var payload map[string]any
	if err := json.Unmarshal(completion.Payload, &payload); err != nil {
		t.Fatalf("unmarshal payload: %v", err)
	}
	checks := map[string]any{
		"tenant_id":                "tenant-1",
		"publication_id":           "EDU-2024-12345",
		"status":                   "completed",
		"public_repository_bucket": "public-bucket",
		"public_repository_prefix": "openinfo/EDU-2024-12345/",
		"sitemap_index_key":        "sitemap/index.xml",
		"sitemap_page_key":         "sitemap/page-1.xml",
		"sitemap_result":           "removed",
		"kind":                     "openinfo",
	}
	for k, want := range checks {
		got, ok := payload[k]
		if !ok {
			t.Errorf("missing payload field %q", k)
		} else if got != want {
			t.Errorf("payload[%q] = %v, want %v", k, got, want)
		}
	}
	if deleted, ok := payload["objects_deleted"].(float64); !ok || int(deleted) != 5 {
		t.Errorf("objects_deleted = %v, want 5", payload["objects_deleted"])
	}
}
