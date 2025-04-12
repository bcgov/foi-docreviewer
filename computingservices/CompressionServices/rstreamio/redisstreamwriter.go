package rstreamio

import (
	"compressionservices/models"
	"context"
	"fmt"
	"log"
	"time"

	"github.com/go-redis/redis/v8"
)

// Assuming you have a global redis client
var rdb *redis.Client

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
func NewRedisStreamWriter(redisClient *redis.Client, streamKey string) *RedisStreamWriter {
	return &RedisStreamWriter{
		rdb:                redisClient,
		notificationStream: streamKey,
	}
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
func (w *RedisStreamWriter) ReadFromStream() {
	ctx := context.Background()

	// XReadGroup is used for reading from the stream as part of a consumer group
	streams, err := w.rdb.XReadGroup(ctx, &redis.XReadGroupArgs{
		Group:    "compression-group", // Replace with your group name
		Consumer: "consumer1",         // Replace with your consumer name
		Streams:  []string{w.notificationStream},
		Block:    0, // Block indefinitely if no message is available
		Count:    1, // Read only 1 message at a time
	}).Result()

	if err != nil {
		log.Printf("Error while reading from the stream: %v", err)
		return
	}

	// Handle the received message
	for _, stream := range streams {
		for _, message := range stream.Messages {
			fmt.Printf("Received message: %v\n", message.Values)
		}
	}
}

// Helper function to convert a boolean to "YES" or "NO" string
func boolToStr(value bool) string {
	if value {
		return "YES"
	}
	return "NO"
}

// import logging
// from utils import redisstreamdb, notification_stream_key
// from rstreamio.message.schemas.notification import NotificationPublishSchema
// #from models import dedupeproducermessage
// from datetime import datetime

// import json

// class redisstreamwriter:

//     rdb = redisstreamdb
//     notificationstream = rdb.Stream(notification_stream_key)

//     def sendnotification(self, message, error=False):
//         try:
//             notification_msg = NotificationPublishSchema()
//             notification_msg.serviceid = "compression"
//             notification_msg.errorflag = self.__booltostr(error)
//             notification_msg.ministryrequestid = message.ministryrequestid
//             notification_msg.createdby = message.createdby
//             notification_msg.createdat = datetime.now().strftime("%m/%d/%Y, %H:%M:%S.%f")
//             notification_msg.batch = message.batch
//             #Additional execution parameters : Begin

//             #Additional execution parameters : End
//             msgid = self.notificationstream.add(notification_msg.__dict__, id="*")
//             logging.info("Notification message for msgid = %s ",  msgid)
//         except RuntimeError as error:
//             print("Exception while sending notification, func sendnotification(p4), Error : {0} ".format(error))
//             logging.error("Unable to write to notification stream for batch %s | ministryrequestid=%i", message.batch, message.ministryrequestid)
//             logging.error(error)

//     def __booltostr(self, value):
//         return "YES" if value == True else "NO"
