package activemq

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"

	"ocrservices/models"

	"github.com/stretchr/testify/require"
)

func TestPushSuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(200) }))
	defer srv.Close()
	err := New(srv.Client(), srv.URL, "u", "p", "foidococr").Push(context.Background(), models.OCRAzureMessage{DocumentMasterID: 1})
	require.NoError(t, err)
}

func TestPush4xxIsPermanent(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(400) }))
	defer srv.Close()
	err := New(srv.Client(), srv.URL, "u", "p", "foidococr").Push(context.Background(), models.OCRAzureMessage{})
	require.Error(t, err)
	require.True(t, IsPermanent(err))
}

func TestPush5xxIsRetryable(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(503) }))
	defer srv.Close()
	err := New(srv.Client(), srv.URL, "u", "p", "foidococr").Push(context.Background(), models.OCRAzureMessage{})
	require.Error(t, err)
	require.False(t, IsPermanent(err))
}

// TestPushRequestDetails verifies that Push sends a POST with Basic Auth,
// application/json content type, destination=queue://foidococr query param,
// and a body that decodes back into the original OCRAzureMessage.
func TestPushRequestDetails(t *testing.T) {
	msg := models.OCRAzureMessage{
		BCGovCode:        "ABC",
		RequestNumber:    "REQ-001",
		DocumentMasterID: 42,
		Trigger:          "manual",
	}

	var capturedReq *http.Request
	var capturedBody []byte

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		capturedReq = r
		capturedBody, _ = io.ReadAll(r.Body)
		w.WriteHeader(200)
	}))
	defer srv.Close()

	err := New(srv.Client(), srv.URL, "testuser", "testpass", "foidococr").Push(context.Background(), msg)
	require.NoError(t, err)
	require.NotNil(t, capturedReq)

	// Verify HTTP method is POST.
	require.Equal(t, http.MethodPost, capturedReq.Method)

	// Verify Basic Authorization header.
	expectedCreds := base64.StdEncoding.EncodeToString([]byte("testuser:testpass"))
	require.Equal(t, "Basic "+expectedCreds, capturedReq.Header.Get("Authorization"))

	// Verify Content-Type is application/json.
	require.Equal(t, "application/json", capturedReq.Header.Get("Content-Type"))

	// Verify destination query parameter.
	require.Equal(t, "queue://foidococr", capturedReq.URL.Query().Get("destination"))

	// Verify body decodes back to the original message.
	var decoded models.OCRAzureMessage
	require.NoError(t, json.Unmarshal(capturedBody, &decoded))
	require.Equal(t, msg, decoded)
}

// errRoundTripper is a deterministic transport that always returns a network error.
type errRoundTripper struct{ err error }

func (e errRoundTripper) RoundTrip(_ *http.Request) (*http.Response, error) { return nil, e.err }

// TestPushTransportErrorIsRetryable verifies that a transport-level error
// (e.g. cancelled context or network failure) is not classified as permanent.
func TestPushTransportErrorIsRetryable(t *testing.T) {
	transport := errRoundTripper{err: fmt.Errorf("connection refused")}
	client := &http.Client{Transport: transport}

	err := New(client, "http://127.0.0.1:1", "u", "p", "foidococr").Push(context.Background(), models.OCRAzureMessage{})
	require.Error(t, err)
	require.False(t, IsPermanent(err), "transport error must be retryable (IsPermanent=false)")
}

// TestPushCancelledContextIsRetryable verifies that a cancelled context error
// is not classified as permanent.
func TestPushCancelledContextIsRetryable(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) { w.WriteHeader(200) }))
	defer srv.Close()

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // cancel immediately

	err := New(srv.Client(), srv.URL, "u", "p", "foidococr").Push(ctx, models.OCRAzureMessage{})
	require.Error(t, err)
	require.False(t, IsPermanent(err), "cancelled context error must be retryable (IsPermanent=false)")
}
