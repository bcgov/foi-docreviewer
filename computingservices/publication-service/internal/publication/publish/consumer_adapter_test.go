package publish

import (
	"context"
	"encoding/json"
	"errors"
	"testing"

	"publication-service/internal/events"
	pub "publication-service/internal/publish"
	"publication-service/internal/sitemapping"
)

type fakePublisher struct {
	result pub.PublishResult
	err    error
}

func (f *fakePublisher) Handle(_ context.Context, _ *Domain) (pub.PublishResult, error) {
	return f.result, f.err
}

type fakeSitemapWriter struct {
	result sitemapping.Result
	err    error
}

func (f *fakeSitemapWriter) Handle(_ context.Context, _ sitemapping.Request) (sitemapping.Result, error) {
	return f.result, f.err
}

func TestConsumerAdapter_OpenInfoCompletionEventType(t *testing.T) {
	adapter := NewCompletionAdapter(
		&fakePublisher{result: pub.PublishResult{PublicationID: "X"}},
		&fakeSitemapWriter{},
	)
	env := goodEnvelope()
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
	if completion.EventType != events.TypePublicationPublishCompleted {
		t.Errorf("EventType = %q", completion.EventType)
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

func TestConsumerAdapter_HandlerPropagatesError(t *testing.T) {
	adapter := NewCompletionAdapter(
		&fakePublisher{err: errors.New("boom")},
		nil,
	)
	env := goodEnvelope()
	_, handler, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if err := handler(context.Background()); err == nil {
		t.Fatal("expected error")
	}
}

func TestConsumerAdapter_KindInClaimInfo(t *testing.T) {
	adapter := NewCompletionAdapter(
		&fakePublisher{result: pub.PublishResult{PublicationID: "X"}},
		&fakeSitemapWriter{},
	)
	env := goodEnvelope()
	info, _, _, err := adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize: %v", err)
	}
	if info.Kind != pub.KindOpenInfo {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindOpenInfo)
	}

	env.Payload = goodPDPayload()
	info, _, _, err = adapter.Normalize(env)
	if err != nil {
		t.Fatalf("Normalize PD: %v", err)
	}
	if info.Kind != pub.KindProactiveDisclosure {
		t.Errorf("ClaimInfo.Kind = %q, want %q", info.Kind, pub.KindProactiveDisclosure)
	}
}
