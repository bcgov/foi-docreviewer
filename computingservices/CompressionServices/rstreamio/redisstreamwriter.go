package rstreamio

import (
	"compressionservices/models"
	"compressionservices/utils"
	"context"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
)

// Assuming you have a global redis client
var rdb = utils.CreateRedisClient()
var streamKey = utils.ViperEnvVariable("NOTIFICATION_STREAM_KEY")

// NotificationPublishSchema is the Go equivalent of your notification schema
type NotificationPublishSchema struct {
	ServiceID         string `json:"serviceid"`
	ErrorFlag         string `json:"errorflag"`
	MinistryRequestID int    `json:"ministryrequestid"`
	CreatedBy         string `json:"createdby"`
	CreatedAt         string `json:"createdat"`
	Batch             string `json:"batch"`
}

// RedisStreamWriter struct holds the stream and other necessary data
type RedisStreamWriter struct {
	rdb                *redis.Client
	notificationStream string
}

// NewRedisStreamWriter initializes and returns a new RedisStreamWriter
func NewRedisStreamWriter(redisClient *redis.Client) *RedisStreamWriter {
	return &RedisStreamWriter{
		rdb:                redisClient,
		notificationStream: streamKey,
	}
}

func SendNotification(message *models.CompressionProducerMessage, errorFlag bool) {
	writer := NewRedisStreamWriter(rdb)
	writer.SendNotification(message, errorFlag)
}

// SendNotification sends a notification to the Redis stream
func (w *RedisStreamWriter) SendNotification(message *models.CompressionProducerMessage, errorFlag bool) {
	ctx := context.Background()

	notificationMsg := map[string]interface{}{
		"serviceid":         "compression",
		"errorflag":         boolToStr(errorFlag),
		"ministryrequestid": message.MinistryRequestID,
		"createdby":         message.CreatedBy,
		"createdat":         time.Now().Format("2006-01-02 15:04:05.000"),
		"batch":             message.Batch,
	}

	// Use XAdd to add message to the Redis stream
	_, err := w.rdb.XAdd(ctx, &redis.XAddArgs{
		Stream: w.notificationStream,
		Values: notificationMsg,
	}).Result()

	if err != nil {
		log.Printf("Unable to write to notification stream for batch %s | ministryrequestid=%d: %v", message.Batch, message.MinistryRequestID, err)
	} else {
		log.Printf("Notification message added to stream for batch %s | ministryrequestid=%d", message.Batch, message.MinistryRequestID)
	}
}

// ReadFromStream reads messages from the Redis stream
// func (w *RedisStreamWriter) ReadFromStream() {
// 	ctx := context.Background()

// 	// XReadGroup is used for reading from the stream as part of a consumer group
// 	streams, err := w.rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
// 		Group:    "compression-group", // Replace with your group name
// 		Consumer: "consumer1",         // Replace with your consumer name
// 		Streams:  []string{w.notificationStream},
// 		Block:    0, // Block indefinitely if no message is available
// 		Count:    1, // Read only 1 message at a time
// 	}).Result()

// 	if err != nil {
// 		log.Printf("Error while reading from the stream: %v", err)
// 		return
// 	}

// 	// Handle the received message
// 	for _, stream := range streams {
// 		for _, message := range stream.Messages {
// 			fmt.Printf("Received message: %v\n", message.Values)
// 		}
// 	}
// }

// Helper function to convert a boolean to "YES" or "NO" string
func boolToStr(value bool) string {
	if value {
		return "YES"
	}
	return "NO"
}
