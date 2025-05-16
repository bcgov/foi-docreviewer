package rstreamio

import (
	"compressionservices/models"
	"compressionservices/utils"
	"context"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
)

var rdb = utils.CreateRedisClient()
var streamKey = utils.ViperEnvVariable("NOTIFICATION_STREAM_KEY")

type NotificationPublishSchema struct {
	ServiceID         string `json:"serviceid"`
	ErrorFlag         string `json:"errorflag"`
	MinistryRequestID int    `json:"ministryrequestid"`
	CreatedBy         string `json:"createdby"`
	CreatedAt         string `json:"createdat"`
	Batch             string `json:"batch"`
}

type RedisStreamWriter struct {
	rdb                *redis.Client
	notificationStream string
}

// Initializes and returns a new RedisStreamWriter
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

	// XAdd to add message to the Redis stream
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

func boolToStr(value bool) string {
	if value {
		return "YES"
	}
	return "NO"
}
