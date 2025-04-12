package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"maps"
	"strconv"
	"time"

	"compressionservices/rstreamio"
	"compressionservices/services"
	"compressionservices/utils"

	"github.com/go-redis/redis/v8"
	//"golang.org/x/exp/maps"
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

func Start(consumerID string, startFrom StartFrom, cfg *utils.Config) {
	STREAM_KEY := cfg.CompressionStreamKey
	fmt.Printf("STREAM_KEY:%s\n", STREAM_KEY)

	rdb := utils.CreateRedisClient()

	stream := STREAM_KEY
	lastIDKey := fmt.Sprintf(LAST_ID_KEY, consumerID)

	lastID, err := rdb.Get(ctx, lastIDKey).Result()
	fmt.Printf("lastID:%s\n", lastID)
	//fmt.Printf("err:%s\n", err)

	// if last_id:
	// 	print(f"Resume from ID: {last_id}")
	// else:
	// 	last_id = start_from.value
	// 	print(f"Starting from {start_from.name}")
	if err == redis.Nil {
		lastID = string(startFrom)
		fmt.Printf("Starting from %s\n", startFrom)
	} else if err == nil {
		fmt.Printf("Resume from ID: %s\n", lastID)
	} else {
		log.Fatalf("Error fetching last ID: %v", err)
	}
	// Create an instance of RedisStreamWriter
	redisStreamWriter := rstreamio.NewRedisStreamWriter(rdb, STREAM_KEY)
	fmt.Printf("where is the rest of it?")
	for {
		fmt.Printf("?????")

		messages, err := rdb.XRead(ctx, &redis.XReadArgs{
			Streams: []string{stream, lastID},
			Block:   BLOCK_TIME,
		}).Result()

		if err != nil && err != redis.Nil {
			fmt.Printf("Error reading stream: %v\n", err)
			continue
		}

		for _, stream := range messages {
			for _, msg := range stream.Messages {
				fmt.Printf("processing-%v\n", msg)

				messageJSON := make(map[string]any)
				maps.Copy(messageJSON, msg.Values)
				casted := castRedisMessage(messageJSON)
				messageBytes, _ := json.Marshal(casted)

				fmt.Printf("messageJSON-%v\n\n", messageJSON)
				fmt.Printf("casted-%v\n\n", casted)

				func() {
					defer func() {
						if r := recover(); r != nil {
							fmt.Printf("Exception while processing redis message, func start(p1), Error : %v\n", r)
						}
					}()
					producermessage, err := utils.GetCompressionProducerMessage(messageBytes)
					if err != nil {
						// Handle error
						fmt.Printf("Error:%v\n", err)
						return
					}
					fmt.Printf("producermessage:%v\n", producermessage)
					services.ProcessMessage(producermessage)
					complete, error := services.IsBatchCompleted(producermessage.Batch)
					if error {
						// Handle error
						fmt.Printf("Error:%v\n", err)
						return
					}
					if complete {
						redisStreamWriter.SendNotification(producermessage, error)
					} else {
						fmt.Printf("batch not yet complete, no message sent")
					}
				}()
				lastID = msg.ID
				rdb.Set(ctx, lastIDKey, lastID, 0)
				fmt.Printf("finished processing %s\n", msg.ID)
			}
		}
	}
}

func castRedisMessage(msg map[string]any) map[string]any {
	result := make(map[string]any)
	for k, v := range msg {
		strVal, _ := v.(string)
		switch k {
		case "inputdocumentmasterid", "jobid":
			intVal, _ := strconv.Atoi(strVal)
			result[k] = intVal
		// case "incompatible":
		// 	boolVal := strVal == "1" || strVal == "true"
		// 	result[k] = boolVal
		default:
			result[k] = strVal
		}
	}
	return result
}
