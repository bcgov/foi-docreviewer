package redislib

import (
	myconfig "OpenInfoServices/config"
	"context"
	"fmt"
	"log"

	"github.com/redis/go-redis/v9"
)

// Initialize a Redis client
func CreateRedisClient() *redis.Client {
	queuehost, queueport, queuepassword := myconfig.GetRedis()

	rdb := redis.NewClient(&redis.Options{
		Addr:     queuehost + ":" + queueport,
		Password: queuepassword,
		DB:       0, // Use default DB
	})
	return rdb
}

// Write a message to the Redis queue
func WriteMessage(rdb *redis.Client, queueName string, message string) {
	err := rdb.LPush(context.Background(), queueName, message).Err()
	if err != nil {
		log.Fatalf("could not write message to queue: %v", err)
	}
	fmt.Printf("Message written to queue: %s\n", message)
}

// Read a message from the Redis queue
func ReadMessage(rdb *redis.Client, queueName string) (string, error) {
	return rdb.RPop(context.Background(), queueName).Result()
}
