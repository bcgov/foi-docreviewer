package compressor

import (
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAWSSignerValidationRejectsUnsafeConfiguration(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name     string
		endpoint string
		region   string
		expiry   time.Duration
	}{
		{name: "unsupported endpoint scheme", endpoint: "ftp://objects.example", region: "ca-central-1", expiry: 15 * time.Minute},
		{name: "endpoint without host", endpoint: "https:///objects", region: "ca-central-1", expiry: 15 * time.Minute},
		{name: "endpoint userinfo", endpoint: "https://user:secret@objects.example", region: "ca-central-1", expiry: 15 * time.Minute},
		{name: "endpoint query", endpoint: "https://objects.example?token=secret", region: "ca-central-1", expiry: 15 * time.Minute},
		{name: "endpoint fragment", endpoint: "https://objects.example#private", region: "ca-central-1", expiry: 15 * time.Minute},
		{name: "blank region", endpoint: "https://objects.example", region: " ", expiry: 15 * time.Minute},
		{name: "zero expiry", endpoint: "https://objects.example", region: "ca-central-1", expiry: 0},
		{name: "expiry above security maximum", endpoint: "https://objects.example", region: "ca-central-1", expiry: 15*time.Minute + time.Nanosecond},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()

			signer, err := NewAWSSigner(test.endpoint, test.region, test.expiry)

			require.Error(t, err)
			assert.Nil(t, signer)
			assert.ErrorIs(t, err, errInvalidS3Configuration)
			assert.NotContains(t, err.Error(), "secret")
		})
	}
}

func TestObjectKeyAcceptsOnlyApprovedForms(t *testing.T) {
	t.Parallel()

	valid := []struct {
		name       string
		objectPath string
		want       string
	}{
		{name: "relative key", objectPath: "folder/input.pdf", want: "folder/input.pdf"},
		{name: "s3 URL", objectPath: "s3://citz-test-e/folder/input.pdf", want: "folder/input.pdf"},
		{name: "legacy path style HTTPS URL", objectPath: "https://objects.example/citz-test-e/folder/input.pdf", want: "folder/input.pdf"},
	}
	for _, test := range valid {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()
			got, err := objectKey("citz-test-e", test.objectPath)
			require.NoError(t, err)
			assert.Equal(t, test.want, got)
		})
	}

	invalid := []struct {
		name       string
		objectPath string
	}{
		{name: "wrong s3 bucket", objectPath: "s3://wrong-bucket/folder/input.pdf"},
		{name: "wrong legacy bucket", objectPath: "https://objects.example/wrong-bucket/folder/input.pdf"},
		{name: "dot segment", objectPath: "folder/./input.pdf"},
		{name: "dot dot segment", objectPath: "folder/../input.pdf"},
		{name: "encoded dot dot segment", objectPath: "folder/%2e%2e/input.pdf"},
		{name: "control character segment", objectPath: "folder/private%0Aname.pdf"},
		{name: "unsupported scheme", objectPath: "ftp://objects.example/citz-test-e/input.pdf"},
		{name: "empty key", objectPath: ""},
		{name: "empty s3 key", objectPath: "s3://citz-test-e"},
		{name: "absolute relative key", objectPath: "/folder/input.pdf"},
		{name: "relative key query", objectPath: "folder/input.pdf?token=secret"},
		{name: "relative key fragment", objectPath: "folder/input.pdf#private"},
		{name: "legacy URL userinfo", objectPath: "https://user:secret@objects.example/citz-test-e/input.pdf"},
	}
	for _, test := range invalid {
		t.Run(test.name, func(t *testing.T) {
			t.Parallel()
			_, err := objectKey("citz-test-e", test.objectPath)
			require.Error(t, err)
			assert.ErrorIs(t, err, errInvalidS3Object)
			assert.NotContains(t, err.Error(), "secret")
		})
	}
}

func TestRemoveURLQueryReturnsOnlySafeHTTPObjectURL(t *testing.T) {
	t.Parallel()

	got, err := removeURLQuery("https://objects.example/citz-test-e/input.pdf?X-Amz-Credential=secret#private")
	require.NoError(t, err)
	assert.Equal(t, "https://objects.example/citz-test-e/input.pdf", got)
	assert.NotContains(t, got, "secret")
	assert.NotContains(t, got, "private")

	for _, rawURL := range []string{
		"https://user:secret@objects.example/citz-test-e/input.pdf?token=secret",
		"ftp://objects.example/citz-test-e/input.pdf?token=secret",
		"https:///citz-test-e/input.pdf?token=secret",
	} {
		_, err := removeURLQuery(rawURL)
		require.Error(t, err)
		assert.ErrorIs(t, err, errInvalidS3Object)
		assert.NotContains(t, err.Error(), "secret")
	}
}
