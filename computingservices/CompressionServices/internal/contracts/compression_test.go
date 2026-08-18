package contracts

import (
	"encoding/json"
	"testing"

	"compressionservices/models"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestCompressionPayloadMatchesPythonProducer(t *testing.T) {
	body := []byte(`{"jobid":41,"s3filepath":"bucket/input.pdf","filename":"input.pdf","ministryrequestid":22,"documentmasterid":7,"trigger":"recordupload","createdby":"user","requestnumber":"REQ-1","batch":"batch-1","incompatible":false,"bcgovcode":"CITZ","attributes":{"isattachment":true,"pages":3},"documentid":9}`)
	var got models.CompressionProducerMessage
	require.NoError(t, json.Unmarshal(body, &got))
	assert.Equal(t, 41, got.JobID)
	assert.Equal(t, true, got.Attributes["isattachment"])
	require.NotNil(t, got.DocumentID)
	assert.Equal(t, 9, *got.DocumentID)
}

func TestCompressionPayloadOptionalFieldsRemainPointers(t *testing.T) {
	body := []byte(`{"jobid":41,"s3filepath":"bucket/input.pdf","filename":"input.pdf","ministryrequestid":22,"documentmasterid":7,"trigger":"recordupload","createdby":"user","requestnumber":"REQ-1","batch":"batch-1","incompatible":false,"bcgovcode":"CITZ","attributes":{},"documentid":9,"outputdocumentmasterid":10,"originaldocumentmasterid":11,"usertoken":"token"}`)
	var got models.CompressionProducerMessage
	require.NoError(t, json.Unmarshal(body, &got))
	require.NotNil(t, got.DocumentID)
	require.NotNil(t, got.OutputDocumentMasterID)
	require.NotNil(t, got.OriginalDocumentMasterID)
	require.NotNil(t, got.UserToken)
	assert.Equal(t, 9, *got.DocumentID)
	assert.Equal(t, 10, *got.OutputDocumentMasterID)
	assert.Equal(t, 11, *got.OriginalDocumentMasterID)
	assert.Equal(t, "token", *got.UserToken)
}

func TestCompressionPayloadOmittedOptionalFieldsRemainNil(t *testing.T) {
	body := []byte(`{"jobid":41,"s3filepath":"bucket/input.pdf","filename":"input.pdf","ministryrequestid":22,"documentmasterid":7,"trigger":"recordupload","createdby":"user","requestnumber":"REQ-1","batch":"batch-1","incompatible":false,"bcgovcode":"CITZ","attributes":{}}`)
	var got models.CompressionProducerMessage
	require.NoError(t, json.Unmarshal(body, &got))
	assert.Nil(t, got.DocumentID)
	assert.Nil(t, got.OutputDocumentMasterID)
	assert.Nil(t, got.OriginalDocumentMasterID)
	assert.Nil(t, got.UserToken)
}

func TestCompressionRequestedUsesProducerContract(t *testing.T) {
	definition := CompressionRequested("compression")
	assert.Equal(t, "compression", definition.Topic)
	assert.Equal(t, CompressionEventType, definition.Type)
	assert.Equal(t, CompressionSchemaVersion, definition.Version)
}
