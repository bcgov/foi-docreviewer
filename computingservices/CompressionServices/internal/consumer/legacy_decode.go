package consumer

import (
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"strconv"
	"strings"

	"compressionservices/internal/compression"
	"compressionservices/internal/config"
	"compressionservices/models"
)

func decodeLegacyMessage(message LegacyMessage, workload config.Workload) (compression.Delivery, error) {
	delivery := compression.Delivery{StreamID: message.ID, Workload: workload}
	jobID, err := legacyInt(message.Values["jobid"], true)
	if err != nil || jobID <= 0 {
		return delivery, errors.New("legacy message job identifier is invalid")
	}
	delivery.Message.JobID = jobID
	values := message.Values
	var decoded models.CompressionProducerMessage
	decoded.JobID = jobID
	if decoded.S3FilePath, err = legacyString(values, "s3filepath", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.Filename, err = legacyString(values, "filename", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.RequestNumber, err = legacyString(values, "requestnumber", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.Batch, err = legacyString(values, "batch", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.BCGovCode, err = legacyString(values, "bcgovcode", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.Trigger, err = legacyString(values, "trigger", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.CreatedBy, err = legacyString(values, "createdby", false); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.CompressedS3FilePath, err = legacyString(values, "compresseds3filepath", true); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.MinistryRequestID, err = legacyInt(values["ministryrequestid"], true); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if decoded.DocumentMasterID, err = legacyInt(values["documentmasterid"], true); err != nil {
		return delivery, malformedLegacy(err, jobID)
	}
	if raw, ok := values["outputdocumentmasterid"]; ok && !isBlankLegacy(raw) {
		v, e := legacyInt(raw, true)
		if e != nil {
			return delivery, malformedLegacy(e, jobID)
		}
		decoded.OutputDocumentMasterID = &v
	}
	if raw, ok := values["originaldocumentmasterid"]; ok && !isBlankLegacy(raw) {
		v, e := legacyInt(raw, true)
		if e != nil {
			return delivery, malformedLegacy(e, jobID)
		}
		decoded.OriginalDocumentMasterID = &v
	}
	if raw, ok := values["documentid"]; ok && !isBlankLegacy(raw) {
		v, e := legacyInt(raw, true)
		if e != nil {
			return delivery, malformedLegacy(e, jobID)
		}
		decoded.DocumentID = &v
	}
	if raw, ok := values["incompatible"]; ok {
		decoded.Incompatible, err = legacyBool(raw)
		if err != nil {
			return delivery, malformedLegacy(err, jobID)
		}
	}
	if raw, ok := values["needsocr"]; ok {
		if _, err = legacyBool(raw); err != nil {
			return delivery, malformedLegacy(err, jobID)
		}
	}
	if raw, ok := values["usertoken"]; ok && !isBlankLegacy(raw) {
		token, e := legacyStringValue(raw)
		if e != nil {
			return delivery, malformedLegacy(e, jobID)
		}
		decoded.UserToken = &token
	}
	if raw, ok := values["attributes"]; ok && !isBlankLegacy(raw) {
		decoded.Attributes, err = legacyAttributes(raw)
		if err != nil {
			return delivery, malformedLegacy(err, jobID)
		}
	} else {
		decoded.Attributes = map[string]any{}
	}
	delivery.Message = decoded
	return delivery, nil
}

func malformedLegacy(err error, jobID int) error {
	return fmt.Errorf("legacy field conversion failed for job %d: %w", jobID, err)
}

func legacyString(values map[string]any, key string, optional bool) (string, error) {
	raw, ok := values[key]
	if !ok || isBlankLegacy(raw) {
		if optional {
			return "", nil
		}
		return "", errors.New("required legacy field missing")
	}
	return legacyStringValue(raw)
}

func legacyStringValue(raw any) (string, error) {
	switch value := raw.(type) {
	case string:
		return value, nil
	case []byte:
		return string(value), nil
	default:
		return "", errors.New("legacy string field has invalid type")
	}
}

func legacyInt(raw any, required bool) (int, error) {
	if raw == nil {
		if required {
			return 0, errors.New("legacy integer field missing")
		}
		return 0, nil
	}
	max := int64(^uint(0) >> 1)
	min := -max - 1
	var value int64
	switch v := raw.(type) {
	case string:
		if strings.TrimSpace(v) == "" {
			return 0, errors.New("legacy integer field is blank")
		}
		parsed, err := strconv.ParseInt(strings.TrimSpace(v), 10, 64)
		if err != nil {
			return 0, errors.New("legacy integer field is invalid")
		}
		value = parsed
	case []byte:
		parsed, err := strconv.ParseInt(strings.TrimSpace(string(v)), 10, 64)
		if err != nil {
			return 0, errors.New("legacy integer field is invalid")
		}
		value = parsed
	case int:
		return v, nil
	case int8:
		value = int64(v)
	case int16:
		value = int64(v)
	case int32:
		value = int64(v)
	case int64:
		value = v
	case uint:
		if uint64(v) > uint64(max) {
			return 0, errors.New("legacy integer field is out of range")
		}
		return int(v), nil
	case uint8:
		return int(v), nil
	case uint16:
		return int(v), nil
	case uint32:
		if uint64(v) > uint64(max) {
			return 0, errors.New("legacy integer field is out of range")
		}
		return int(v), nil
	case uint64:
		if v > uint64(max) {
			return 0, errors.New("legacy integer field is out of range")
		}
		return int(v), nil
	case float32:
		return legacyFloatInt(float64(v), min, max)
	case float64:
		return legacyFloatInt(v, min, max)
	default:
		return 0, errors.New("legacy integer field has invalid type")
	}
	if value < min || value > max {
		return 0, errors.New("legacy integer field is out of range")
	}
	return int(value), nil
}

func legacyFloatInt(value float64, min, max int64) (int, error) {
	if math.IsNaN(value) || math.IsInf(value, 0) || value != math.Trunc(value) || value < float64(min) || value >= float64(max) {
		return 0, errors.New("legacy integer field is invalid")
	}
	return int(value), nil
}

func legacyBool(raw any) (bool, error) {
	switch value := raw.(type) {
	case bool:
		return value, nil
	case string:
		switch strings.ToLower(strings.TrimSpace(value)) {
		case "1", "true":
			return true, nil
		case "0", "false":
			return false, nil
		}
	case []byte:
		return legacyBool(string(value))
	case int, int8, int16, int32, int64:
		v, _ := legacyInt(value, true)
		if v == 0 || v == 1 {
			return v == 1, nil
		}
	}
	return false, errors.New("legacy boolean field is invalid")
}

func legacyAttributes(raw any) (map[string]any, error) {
	text, err := legacyStringValue(raw)
	if err != nil {
		return nil, errors.New("legacy attributes must be JSON")
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(text), &decoded); err != nil || decoded == nil {
		return nil, errors.New("legacy attributes JSON is invalid")
	}
	for key, value := range decoded {
		switch key {
		case "filesize", "compressedsize", "convertedfilesize":
			v, err := legacyInt(value, true)
			if err != nil {
				return nil, errors.New("legacy attribute numeric field is invalid")
			}
			decoded[key] = v
		case "incompatible", "isattachment":
			v, err := legacyBool(value)
			if err != nil {
				return nil, errors.New("legacy attribute boolean field is invalid")
			}
			decoded[key] = v
		case "divisions":
			v, err := legacyDivisions(value)
			if err != nil {
				return nil, errors.New("legacy divisions field is invalid")
			}
			decoded[key] = v
		}
	}
	return decoded, nil
}

func legacyDivisions(raw any) ([]models.Division, error) {
	items, ok := raw.([]any)
	if !ok {
		return nil, errors.New("legacy divisions collection is invalid")
	}
	result := make([]models.Division, 0, len(items))
	for _, item := range items {
		object, ok := item.(map[string]any)
		if !ok {
			return nil, errors.New("legacy division item is invalid")
		}
		id, ok := object["divisionid"]
		if !ok {
			return nil, errors.New("legacy division identifier is missing")
		}
		value, err := legacyInt(id, true)
		if err != nil {
			return nil, err
		}
		result = append(result, models.Division{DivisionID: value})
	}
	return result, nil
}

func isBlankLegacy(value any) bool {
	if value == nil {
		return true
	}
	if text, ok := value.(string); ok {
		return strings.TrimSpace(text) == ""
	}
	if bytes, ok := value.([]byte); ok {
		return strings.TrimSpace(string(bytes)) == ""
	}
	return false
}
