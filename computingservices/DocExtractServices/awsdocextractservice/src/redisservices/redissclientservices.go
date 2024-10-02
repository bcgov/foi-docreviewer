package redisservices

import (
	"context"
	"log"

	"github.com/go-redis/redis/v8"
)

var ctx = context.Background()

type FOIRedisClient struct {
	client *redis.Client
}

// NewRedisClient creates a new Redis client
func CreateFOIRedisClient(addr string, password string, db int) *FOIRedisClient {
	rdb := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password, // no password set
		DB:       db,       // use default DB
	})

	// Ping the Redis server to verify connection
	if err := rdb.Ping(ctx).Err(); err != nil {
		log.Fatalf("could not connect to redis: %v", err)
	}

	return &FOIRedisClient{client: rdb}
}

// Set stores a key-value pair in Redis
func (r *FOIRedisClient) Set(key string, value interface{}) error {
	return r.client.Set(ctx, key, value, 0).Err()
}

// Get retrieves a value by key from Redis
func (r *FOIRedisClient) Get(key string) (string, error) {
	val, err := r.client.Get(ctx, key).Result()
	if err == redis.Nil {
		return "", nil // Key does not exist
	} else if err != nil {
		return "", err
	}
	return val, nil
}

// Close shuts down the Redis client
func (r *FOIRedisClient) Close() {
	r.client.Close()
}
