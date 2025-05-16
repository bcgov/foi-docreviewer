// # import json
// # from models import compressionproducermessage, s3credentials

// # def getcompressionproducermessage(producer_json):
// #     j = json.loads(producer_json)
// #     messageobject = compressionproducermessage(**j)
// #     return messageobject

// # def gets3credentialsobject(s3cred_json):
// #     j = json.loads(s3cred_json)
// #     messageobject = s3credentials(**j)
// #     return messageobject

package utils

import (
	"encoding/json"
	"fmt"

	"ocrservices/models"
)

func GetOCRProducerMessage(producerJSON []byte) (*models.OCRProducerMessage, error) {
	var messageObject models.OCRProducerMessage
	err := json.Unmarshal(producerJSON, &messageObject)
	if err != nil {
		return nil, fmt.Errorf("error decoding OCR producer message: %v", err)
	}
	return &messageObject, nil
}

func GetS3CredentialsObject(s3CredJSON string) (*models.S3Credentials, error) {
	var messageObject models.S3Credentials
	err := json.Unmarshal([]byte(s3CredJSON), &messageObject)
	if err != nil {
		return nil, fmt.Errorf("error decoding s3 credentials: %v", err)
	}
	return &messageObject, nil
}
