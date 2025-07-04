package services

import (
	"compressionservices/models"
	"compressionservices/utils"
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"github.com/go-redis/redis/v8"
)

var (
	ocrRedisHost        = utils.ViperEnvVariable("REDIS_HOST")
	ocrRedisPort        = utils.ViperEnvVariable("REDIS_PORT")
	ocrRedisPassword    = utils.ViperEnvVariable("REDIS_PASSWORD")
	ocrStreamKey        = utils.ViperEnvVariable("OCR_STREAM_KEY")
	healthCheckInterval = utils.ViperEnvVariable("HEALTH_CHECK_INTERVAL")
)

type OCRProducerMessage struct {
	JobID   int    `json:"jobid"`
	Message string `json:"message"`
}

type OCRProducerService struct {
	redisClient *redis.Client
	streamKey   string
}

func NewOCRProducerService() *OCRProducerService {
	port, _ := strconv.Atoi(ocrRedisPort)
	hcInterval, _ := strconv.Atoi(healthCheckInterval)

	rdb := redis.NewClient(&redis.Options{
		Addr:         fmt.Sprintf("%s:%d", ocrRedisHost, port),
		Password:     ocrRedisPassword,
		DB:           0,
		ReadTimeout:  time.Second * time.Duration(hcInterval),
		WriteTimeout: time.Second * 10,
	})

	return &OCRProducerService{
		redisClient: rdb,
		streamKey:   ocrStreamKey,
	}
}

func (s *OCRProducerService) ProduceOCREvent(finalMessage *models.CompressionProducerMessage, jobID int) (string, error) {
	ctx := context.Background()
	//msg := finalMessage
	// OCRProducerMessage{
	// 	JobID:   jobID,
	// 	Message: finalMessage,
	// }

	//fmt.Println("OCR Stream Key:", s.streamKey)

	// Convert struct to map[string]interface{} for Redis XAdd
	msgBytes, err := json.Marshal(finalMessage)
	if err != nil {
		return "", fmt.Errorf("error marshalling finalMessage: %w", err)
	}

	var rawMap map[string]interface{}
	if err := json.Unmarshal(msgBytes, &rawMap); err != nil {
		return "", fmt.Errorf("error unmarshalling to map: %w", err)
	}

	msgMap := make(map[string]interface{})
	for key, val := range rawMap {
		msgMap[key] = fmt.Sprintf("%v", val) // Ensures all values are strings
	}

	// Add to stream
	args := &redis.XAddArgs{
		Stream: s.streamKey,
		Values: msgMap,
	}

	id, err := s.redisClient.XAdd(ctx, args).Result()
	if err != nil {
		return "", fmt.Errorf("error writing to stream: %v", err)
	}
	return id, nil
}
