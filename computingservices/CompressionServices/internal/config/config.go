// Package config loads the CompressionServices runtime configuration.
package config

import (
	"fmt"
	"math"
	"net"
	"strconv"
	"strings"
	"time"
)

type Mode string

const (
	ModeLegacy   Mode = "legacy"
	ModeStandard Mode = "standard"
)

type Workload string

const (
	WorkloadNormal Workload = "normal"
	WorkloadLarge  Workload = "large"
)

type Messaging struct {
	RedisAddress        string
	RedisPassword       string
	StreamPrefix        string
	Topic               string
	ConsumerGroup       string
	LegacyStreamKey     string
	LegacyCheckpointKey string
	ClaimInterval       time.Duration
	ClaimMinIdle        time.Duration
	MaxDeliveryAttempts int
	ShutdownTimeout     time.Duration
}

type Reconciliation struct {
	NormalAfter  time.Duration
	LargeAfter   time.Duration
	UnknownAfter time.Duration
	BatchSize    int
}

type Database struct {
	Host     string
	Port     int
	Name     string
	User     string
	Password string
}

type S3 struct {
	Endpoint      string
	Region        string
	Environment   string
	PresignExpiry time.Duration
}

type Config struct {
	Mode                      Mode
	Workload                  Workload
	ProcessingTimeout         time.Duration
	Messaging                 Messaging
	Database                  Database
	S3                        S3
	Reconciliation            Reconciliation
	CompressionRatioThreshold float64
	OCRStreamKey              string
}

const (
	defaultClaimInterval         = 30 * time.Second
	defaultNormalClaimMinIdle    = 17 * time.Minute
	defaultLargeClaimMinIdle     = 62 * time.Minute
	defaultNormalProcessTimeout  = 15 * time.Minute
	defaultLargeProcessTimeout   = 60 * time.Minute
	defaultNormalReconcileAfter  = 20 * time.Minute
	defaultLargeReconcileAfter   = 75 * time.Minute
	defaultUnknownReconcileAfter = 75 * time.Minute
	defaultReconciliationBatch   = 100
	defaultMaxDeliveryAttempts   = 5
	defaultShutdownTimeout       = 25 * time.Second
	defaultPresignExpiry         = 15 * time.Minute
	defaultCompressionRatio      = 0.9
)

func Load(getenv func(string) string) (Config, error) {
	if getenv == nil {
		return Config{}, fmt.Errorf("getenv is required")
	}

	mode, err := loadMode(getenv)
	if err != nil {
		return Config{}, err
	}

	workload, err := loadWorkload(getenv)
	if err != nil {
		return Config{}, err
	}

	processingDefault := defaultNormalProcessTimeout
	claimMinIdleDefault := defaultNormalClaimMinIdle
	if workload == WorkloadLarge {
		processingDefault = defaultLargeProcessTimeout
		claimMinIdleDefault = defaultLargeClaimMinIdle
	}

	processingTimeout, err := duration(getenv, "COMPRESSION_PROCESSING_TIMEOUT", processingDefault)
	if err != nil {
		return Config{}, err
	}

	claimInterval, err := duration(getenv, "MESSAGING_CLAIM_INTERVAL", defaultClaimInterval)
	if err != nil {
		return Config{}, err
	}
	claimMinIdle, err := duration(getenv, "MESSAGING_CLAIM_MIN_IDLE", claimMinIdleDefault)
	if err != nil {
		return Config{}, err
	}
	if claimMinIdle <= processingTimeout {
		return Config{}, fmt.Errorf("MESSAGING_CLAIM_MIN_IDLE must exceed COMPRESSION_PROCESSING_TIMEOUT")
	}

	normalAfter, err := duration(getenv, "COMPRESSION_RECONCILIATION_NORMAL_AFTER", defaultNormalReconcileAfter)
	if err != nil {
		return Config{}, err
	}
	largeAfter, err := duration(getenv, "COMPRESSION_RECONCILIATION_LARGE_AFTER", defaultLargeReconcileAfter)
	if err != nil {
		return Config{}, err
	}
	unknownAfter, err := duration(getenv, "COMPRESSION_RECONCILIATION_UNKNOWN_AFTER", defaultUnknownReconcileAfter)
	if err != nil {
		return Config{}, err
	}
	normalClaimMinIdle := defaultNormalClaimMinIdle
	largeClaimMinIdle := defaultLargeClaimMinIdle
	if workload == WorkloadNormal {
		normalClaimMinIdle = claimMinIdle
	}
	if workload == WorkloadLarge {
		largeClaimMinIdle = claimMinIdle
	}
	if normalAfter <= normalClaimMinIdle {
		return Config{}, fmt.Errorf("COMPRESSION_RECONCILIATION_NORMAL_AFTER must exceed its claim idle budget")
	}
	if largeAfter <= largeClaimMinIdle {
		return Config{}, fmt.Errorf("COMPRESSION_RECONCILIATION_LARGE_AFTER must exceed its claim idle budget")
	}
	if unknownAfter <= largeClaimMinIdle {
		return Config{}, fmt.Errorf("COMPRESSION_RECONCILIATION_UNKNOWN_AFTER must exceed its claim idle budget")
	}

	maxDeliveryAttempts, err := positiveInt(getenv, "MESSAGING_MAX_DELIVERY_ATTEMPTS", defaultMaxDeliveryAttempts)
	if err != nil {
		return Config{}, err
	}
	shutdownTimeout, err := duration(getenv, "MESSAGING_SHUTDOWN_TIMEOUT", defaultShutdownTimeout)
	if err != nil {
		return Config{}, err
	}
	reconciliationBatch, err := positiveInt(getenv, "COMPRESSION_RECONCILIATION_BATCH_SIZE", defaultReconciliationBatch)
	if err != nil {
		return Config{}, err
	}
	presignExpiry, err := duration(getenv, "COMPRESSION_S3_PRESIGN_EXPIRY", defaultPresignExpiry)
	if err != nil {
		return Config{}, err
	}
	if presignExpiry > defaultPresignExpiry {
		return Config{}, fmt.Errorf("COMPRESSION_S3_PRESIGN_EXPIRY must not exceed 15 minutes")
	}
	ratio, err := floatValue(getenv, "COMPRESSION_RATIO_THRESHOLD", defaultCompressionRatio)
	if err != nil {
		return Config{}, err
	}

	redisHost, err := required(getenv, "REDIS_HOST")
	if err != nil {
		return Config{}, err
	}
	redisPort, err := port(getenv, "REDIS_PORT")
	if err != nil {
		return Config{}, err
	}
	database, err := loadDatabase(getenv)
	if err != nil {
		return Config{}, err
	}
	s3, err := loadS3(getenv, presignExpiry)
	if err != nil {
		return Config{}, err
	}

	messaging := Messaging{
		RedisAddress:        net.JoinHostPort(redisHost, strconv.Itoa(redisPort)),
		RedisPassword:       getenv("REDIS_PASSWORD"),
		ClaimInterval:       claimInterval,
		ClaimMinIdle:        claimMinIdle,
		MaxDeliveryAttempts: maxDeliveryAttempts,
		ShutdownTimeout:     shutdownTimeout,
	}
	if err := loadModeSettings(getenv, mode, &messaging); err != nil {
		return Config{}, err
	}

	return Config{
		Mode:              mode,
		Workload:          workload,
		ProcessingTimeout: processingTimeout,
		Messaging:         messaging,
		Database:          database,
		S3:                s3,
		Reconciliation: Reconciliation{
			NormalAfter:  normalAfter,
			LargeAfter:   largeAfter,
			UnknownAfter: unknownAfter,
			BatchSize:    reconciliationBatch,
		},
		CompressionRatioThreshold: ratio,
		OCRStreamKey:              strings.TrimSpace(getenv("OCR_STREAM_KEY")),
	}, nil
}

func loadMode(getenv func(string) string) (Mode, error) {
	value, err := required(getenv, "COMPRESSION_MESSAGING_MODE")
	if err != nil {
		return "", err
	}

	mode := Mode(value)
	switch mode {
	case ModeLegacy, ModeStandard:
		return mode, nil
	default:
		return "", fmt.Errorf("COMPRESSION_MESSAGING_MODE must be legacy or standard")
	}
}

func loadWorkload(getenv func(string) string) (Workload, error) {
	value, err := required(getenv, "COMPRESSION_WORKLOAD")
	if err != nil {
		return "", err
	}

	workload := Workload(value)
	switch workload {
	case WorkloadNormal, WorkloadLarge:
		return workload, nil
	default:
		return "", fmt.Errorf("COMPRESSION_WORKLOAD must be normal or large")
	}
}

func loadModeSettings(getenv func(string) string, mode Mode, messaging *Messaging) error {
	if mode == ModeStandard {
		streamPrefix, err := required(getenv, "MESSAGING_STREAM_PREFIX")
		if err != nil {
			return err
		}
		topic, err := required(getenv, "COMPRESSION_TOPIC")
		if err != nil {
			return err
		}
		consumerGroup, err := required(getenv, "MESSAGING_CONSUMER_GROUP")
		if err != nil {
			return err
		}
		messaging.StreamPrefix = streamPrefix
		messaging.Topic = topic
		messaging.ConsumerGroup = consumerGroup
		return nil
	}

	streamKey, err := required(getenv, "COMPRESSION_STREAM_KEY")
	if err != nil {
		return err
	}
	checkpointKey, err := required(getenv, "COMPRESSION_CHECKPOINT_KEY")
	if err != nil {
		return err
	}
	messaging.LegacyStreamKey = streamKey
	messaging.LegacyCheckpointKey = checkpointKey
	return nil
}

func loadDatabase(getenv func(string) string) (Database, error) {
	host, err := required(getenv, "COMPRESSION_DB_HOST")
	if err != nil {
		return Database{}, err
	}
	port, err := port(getenv, "COMPRESSION_DB_PORT")
	if err != nil {
		return Database{}, err
	}
	name, err := required(getenv, "COMPRESSION_DB_NAME")
	if err != nil {
		return Database{}, err
	}
	user, err := required(getenv, "COMPRESSION_DB_USER")
	if err != nil {
		return Database{}, err
	}
	password, err := requiredSecret(getenv, "COMPRESSION_DB_PASSWORD")
	if err != nil {
		return Database{}, err
	}

	return Database{Host: host, Port: port, Name: name, User: user, Password: password}, nil
}

func loadS3(getenv func(string) string, presignExpiry time.Duration) (S3, error) {
	endpoint, err := required(getenv, "COMPRESSION_S3_HOST")
	if err != nil {
		return S3{}, err
	}
	region, err := required(getenv, "COMPRESSION_S3_REGION")
	if err != nil {
		return S3{}, err
	}
	environment, err := required(getenv, "COMPRESSION_S3_ENV")
	if err != nil {
		return S3{}, err
	}

	return S3{Endpoint: endpoint, Region: region, Environment: environment, PresignExpiry: presignExpiry}, nil
}

func required(getenv func(string) string, key string) (string, error) {
	value := strings.TrimSpace(getenv(key))
	if value == "" {
		return "", fmt.Errorf("%s is required", key)
	}
	return value, nil
}

func requiredSecret(getenv func(string) string, key string) (string, error) {
	value := getenv(key)
	if strings.TrimSpace(value) == "" {
		return "", fmt.Errorf("%s is required", key)
	}
	return value, nil
}

func duration(getenv func(string) string, key string, defaultValue time.Duration) (time.Duration, error) {
	value := strings.TrimSpace(getenv(key))
	if value == "" {
		return defaultValue, nil
	}
	parsed, err := time.ParseDuration(value)
	if err != nil || parsed <= 0 {
		return 0, fmt.Errorf("%s must be a positive duration", key)
	}
	return parsed, nil
}

func positiveInt(getenv func(string) string, key string, defaultValue int) (int, error) {
	value := strings.TrimSpace(getenv(key))
	if value == "" && defaultValue > 0 {
		return defaultValue, nil
	}
	if value == "" {
		return 0, fmt.Errorf("%s is required", key)
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed <= 0 {
		return 0, fmt.Errorf("%s must be a positive integer", key)
	}
	return parsed, nil
}

func port(getenv func(string) string, key string) (int, error) {
	value := strings.TrimSpace(getenv(key))
	if value == "" {
		return 0, fmt.Errorf("%s is required", key)
	}
	parsed, err := strconv.Atoi(value)
	if err != nil || parsed < 1 || parsed > 65535 {
		return 0, fmt.Errorf("%s must be a valid TCP port", key)
	}
	return parsed, nil
}

func floatValue(getenv func(string) string, key string, defaultValue float64) (float64, error) {
	value := strings.TrimSpace(getenv(key))
	if value == "" {
		return defaultValue, nil
	}
	parsed, err := strconv.ParseFloat(value, 64)
	if err != nil || math.IsNaN(parsed) || math.IsInf(parsed, 0) || parsed <= 0 || parsed > 1 {
		return 0, fmt.Errorf("%s must be a finite value greater than zero and at most one", key)
	}
	return parsed, nil
}
