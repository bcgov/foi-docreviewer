package rstreamio

import (
	"context"
	"log"
	"time"

	"compressionservices/models"

	"github.com/go-redis/redis/v8"
)

type NotificationPublishSchema struct {
	ServiceID         string `json:"serviceid"`
	ErrorFlag         string `json:"errorflag"`
	MinistryRequestID int    `json:"ministryrequestid"`
	CreatedBy         string `json:"createdby"`
	CreatedAt         string `json:"createdat"`
	Batch             string `json:"batch"`
}

// RedisStreamWriter publishes the existing flat notification message contract.
// Its Redis client and target stream are explicitly owned by the caller.
type RedisStreamWriter struct {
	rdb                *redis.Client
	notificationStream string
}

func NewRedisStreamWriter(redisClient *redis.Client, notificationStream string) *RedisStreamWriter {
	return &RedisStreamWriter{rdb: redisClient, notificationStream: notificationStream}
}

func (w *RedisStreamWriter) SendNotification(message *models.CompressionProducerMessage, errorFlag bool) {
	if w == nil || w.rdb == nil || message == nil {
		return
	}
	notificationMsg := map[string]interface{}{
		"serviceid":         "compression",
		"errorflag":         boolToStr(errorFlag),
		"ministryrequestid": message.MinistryRequestID,
		"createdby":         message.CreatedBy,
		"createdat":         time.Now().Format("2006-01-02 15:04:05.000"),
		"batch":             message.Batch,
	}
	if _, err := w.rdb.XAdd(context.Background(), &redis.XAddArgs{Stream: w.notificationStream, Values: notificationMsg}).Result(); err != nil {
		log.Print("Unable to write notification message")
	}
}

func boolToStr(value bool) string {
	if value {
		return "YES"
	}
	return "NO"
}
