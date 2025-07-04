package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"maps"
	"strconv"
	"time"

	"ocrservices/models"
	"ocrservices/services"
	"ocrservices/utils"

	"github.com/go-redis/redis/v8"
)

var (
	ctx         = context.Background()
	LAST_ID_KEY = "%s:lastid"
	BLOCK_TIME  = 5 * time.Second
	//STREAM_KEY  = CompressionStreamKey
)

type StartFrom string

const (
	Beginning StartFrom = "0"
	Latest    StartFrom = "$"
)

func Start(consumerID string, startFrom StartFrom) {
	streamKey := utils.ViperEnvVariable("OCR_STREAM_KEY")
	fmt.Printf("STREAM_KEY: %s\n", streamKey)

	rdb := utils.CreateRedisClient()
	lastIDKey := fmt.Sprintf(LAST_ID_KEY, consumerID)
	lastID := fetchLastID(rdb, lastIDKey, startFrom)
	for {
		messages, err := readStream(rdb, streamKey, lastID)
		if err != nil && err != redis.Nil {
			fmt.Printf("Error reading stream: %v\n", err)
			continue
		}
		for _, stream := range messages {
			for _, msg := range stream.Messages {
				if err := processStreamMessage(rdb, lastIDKey, msg); err != nil {
					fmt.Printf("Error processing message ID %s: %v\n", msg.ID, err)
					//continue // skip this message, don't stop entire processing
				}
				lastID = msg.ID
			}
		}
	}
}

func fetchLastID(rdb *redis.Client, lastIDKey string, startFrom StartFrom) string {
	lastID, err := rdb.Get(ctx, lastIDKey).Result()
	if err == redis.Nil {
		fmt.Printf("Starting from %s\n", startFrom)
		return string(startFrom)
	} else if err != nil {
		log.Fatalf("Error fetching last ID: %v", err)
	}
	fmt.Printf("Resume from ID: %s\n", lastID)
	return lastID
}

func readStream(rdb *redis.Client, stream, lastID string) ([]redis.XStream, error) {
	return rdb.XRead(ctx, &redis.XReadArgs{
		Streams: []string{stream, lastID},
		Block:   BLOCK_TIME,
	}).Result()
}

func processStreamMessage(rdb *redis.Client, lastIDKey string, msg redis.XMessage) error {
	defer func() {
		if r := recover(); r != nil {
			fmt.Printf("Recovered from panic while processing message ID %s: %v\n", msg.ID, r)
		}
	}()
	//fmt.Printf("Processing message: %v\n\n", msg)
	messageJSON := make(map[string]any)
	maps.Copy(messageJSON, msg.Values)
	casted := castRedisMessage(messageJSON)
	//fmt.Printf("casted: %v\n", casted)
	messageBytes, err := json.Marshal(casted)
	if err != nil {
		return fmt.Errorf("error marshaling message: %w", err)
	}
	producerMessage, err := utils.GetOCRProducerMessage(messageBytes)
	if err != nil {
		return fmt.Errorf("error decoding producer message: %w", err)
	}
	//fmt.Printf("producerMessage: %v\n", producerMessage)
	// Only now — after all success — process the message
	services.ProcessMessage(producerMessage)
	complete, hasError := services.IsBatchCompleted(producerMessage.Batch)
	if hasError {
		fmt.Printf("Batch not yet complete")
	}
	fmt.Printf("Batch completed:%v\n", complete)
	//Placeholder for notification logic
	// if complete {
	// 	rstreamio.SendNotification(producerMessage, hasError)
	// } else {
	// 	fmt.Printf("Batch not yet complete, no message sent")
	// }
	// Update last processed ID
	if err := rdb.Set(ctx, lastIDKey, msg.ID, 0).Err(); err != nil {
		return fmt.Errorf("error saving last ID to Redis: %w", err)
	}
	fmt.Printf("Finished processing message ID %s\n", msg.ID)
	return nil
}

func castRedisMessage(msg map[string]any) map[string]any {
	result := make(map[string]any)
	for k, v := range msg {
		result[k] = castField(k, v)
	}
	return result
}

func castField(key string, value any) any {
	strVal, _ := value.(string)
	switch key {
	case "jobid", "ministryrequestid", "documentmasterid",
		"outputdocumentmasterid", "originaldocumentmasterid", "documentid":
		return parseInt(strVal)
	case "attributes":
		switch v := value.(type) {
		case string:
			return parseAttributes(v) // stringified JSON — parse normally
		case map[string]any:
			return castAttributesMap(v) // already decoded — just cast fields
		default:
			return value // fallback
		}
		//return parseAttributes(strVal)
	case "incompatible", "needsocr":
		return castBool(value)
	default:
		return strVal
	}
}

func castAttributesMap(raw map[string]any) map[string]any {
	parsed := make(map[string]any)
	for k, v := range raw {
		parsed[k] = castAttributeField(k, v)
	}
	return parsed
}

func parseInt(s string) int {
	i, _ := strconv.Atoi(s)
	return i
}

//	func parseAttributes(attrStr string) any {
//		fmt.Printf("attrStr: %s\n", attrStr)
//		var raw map[string]any
//		if err := json.Unmarshal([]byte(attrStr), &raw); err != nil {
//			// Log it or return nil, not the raw string
//			fmt.Printf("Warning: Failed to parse attributes JSON: %v\n", err)
//			return nil // or return empty map[string]any{}
//		}
//		parsed := make(map[string]any)
//		for k, v := range raw {
//			parsed[k] = castAttributeField(k, v)
//		}
//		return parsed
//	}
func parseAttributes(attrStr string) any {
	var raw map[string]any
	if err := json.Unmarshal([]byte(attrStr), &raw); err != nil {
		return attrStr // fallback if not valid JSON
	}
	parsed := make(map[string]any)
	for k, v := range raw {
		parsed[k] = castAttributeField(k, v)
	}
	return parsed
}

func castAttributeField(key string, value any) any {
	switch key {
	case "filesize", "compressedsize", "convertedfilesize":
		return castNumeric(value)
	case "incompatible", "isattachment":
		return castBool(value)
	case "divisions":
		return castDivisions(value)
	default:
		return value
	}
}

func castNumeric(v any) int {
	switch val := v.(type) {
	case string:
		i, _ := strconv.Atoi(val)
		return i
	case float64:
		return int(val)
	default:
		return 0
	}
}

func castBool(v any) bool {
	switch val := v.(type) {
	case string:
		return val == "1" || val == "true"
	case bool:
		return val
	default:
		return false
	}
}

func castDivisions(v any) []models.Division {
	divisions := []models.Division{}
	items, ok := v.([]any)
	if !ok {
		return divisions
	}
	for _, item := range items {
		if itemMap, ok := item.(map[string]any); ok {
			id := castDivisionID(itemMap["divisionid"])
			divisions = append(divisions, models.Division{DivisionID: id})
		}
	}
	return divisions
}

func castDivisionID(v any) int {
	switch val := v.(type) {
	case string:
		i, _ := strconv.Atoi(val)
		return i
	case float64:
		return int(val)
	default:
		return 0
	}
}
