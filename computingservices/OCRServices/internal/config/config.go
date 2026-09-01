package config

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

// Config is the fully-validated OCRServices runtime configuration.
type Config struct {
	Messaging         Messaging
	Database          Database
	ActiveMQ          ActiveMQ
	ProcessingTimeout time.Duration
}

type Messaging struct {
	StreamPrefix        string
	ConsumerGroup       string
	ConsumerName        string
	RedisAddress        string
	RedisPassword       string
	ClaimInterval       time.Duration
	ClaimMinIdle        time.Duration
	MaxDeliveryAttempts int
	ShutdownTimeout     time.Duration
}

type Database struct{ Host, Port, User, Password, Name string }

type ActiveMQ struct{ URL, Username, Password, Destination string }

// Load reads and validates configuration from getenv.
func Load(getenv func(string) string) (Config, error) {
	if getenv == nil {
		return Config{}, errors.New("getenv is required")
	}
	claimInterval, err := parseDuration(getenv, "MESSAGING_CLAIM_INTERVAL")
	if err != nil {
		return Config{}, err
	}
	claimMinIdle, err := parseDuration(getenv, "MESSAGING_CLAIM_MIN_IDLE")
	if err != nil {
		return Config{}, err
	}
	shutdown, err := parseDuration(getenv, "MESSAGING_SHUTDOWN_TIMEOUT")
	if err != nil {
		return Config{}, err
	}
	processing, err := parseDuration(getenv, "OCR_PROCESSING_TIMEOUT")
	if err != nil {
		return Config{}, err
	}
	attempts, err := strconv.Atoi(strings.TrimSpace(getenv("MESSAGING_MAX_DELIVERY_ATTEMPTS")))
	if err != nil {
		return Config{}, fmt.Errorf("MESSAGING_MAX_DELIVERY_ATTEMPTS invalid: %w", err)
	}
	consumerName := strings.TrimSpace(getenv("OCR_CONSUMER_NAME"))
	if consumerName == "" {
		consumerName, _ = os.Hostname()
	}
	cfg := Config{
		Messaging: Messaging{
			StreamPrefix:        strings.TrimSpace(getenv("MESSAGING_STREAM_PREFIX")),
			ConsumerGroup:       strings.TrimSpace(getenv("MESSAGING_CONSUMER_GROUP")),
			ConsumerName:        consumerName,
			RedisAddress:        fmt.Sprintf("%s:%s", strings.TrimSpace(getenv("REDIS_HOST")), strings.TrimSpace(getenv("REDIS_PORT"))),
			RedisPassword:       getenv("REDIS_PASSWORD"),
			ClaimInterval:       claimInterval,
			ClaimMinIdle:        claimMinIdle,
			MaxDeliveryAttempts: attempts,
			ShutdownTimeout:     shutdown,
		},
		Database: Database{
			Host:     strings.TrimSpace(getenv("OCR_DB_HOST")),
			Port:     strings.TrimSpace(getenv("OCR_DB_PORT")),
			User:     strings.TrimSpace(getenv("OCR_DB_USER")),
			Password: getenv("OCR_DB_PASSWORD"),
			Name:     strings.TrimSpace(getenv("OCR_DB_NAME")),
		},
		ActiveMQ: ActiveMQ{
			URL:         strings.TrimSpace(getenv("ACTIVEMQ_URL")),
			Username:    getenv("ACTIVEMQ_USERNAME"),
			Password:    getenv("ACTIVEMQ_PASSWORD"),
			Destination: strings.TrimSpace(getenv("ACTIVEMQ_DESTINATION")),
		},
		ProcessingTimeout: processing,
	}
	if err := validate(cfg); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func validate(cfg Config) error {
	m := cfg.Messaging
	if m.StreamPrefix != "foi" {
		return errors.New("MESSAGING_STREAM_PREFIX must be foi")
	}
	if m.ConsumerGroup == "" {
		return errors.New("MESSAGING_CONSUMER_GROUP is required")
	}
	if m.ConsumerName == "" {
		return errors.New("OCR_CONSUMER_NAME (or HOSTNAME) is required")
	}
	host, port, _ := strings.Cut(m.RedisAddress, ":")
	if host == "" {
		return errors.New("REDIS_HOST is required")
	}
	if port == "" {
		return errors.New("REDIS_PORT is required")
	}
	if cfg.ProcessingTimeout <= 0 || m.ClaimInterval <= 0 || m.ClaimMinIdle <= 0 || m.ShutdownTimeout <= 0 {
		return errors.New("durations must be positive")
	}
	if m.ClaimMinIdle < m.ClaimInterval {
		return errors.New("claim min idle must not be shorter than claim interval")
	}
	if m.ClaimMinIdle <= cfg.ProcessingTimeout {
		return errors.New("claim min idle must exceed processing timeout")
	}
	if m.MaxDeliveryAttempts <= 0 {
		return errors.New("MESSAGING_MAX_DELIVERY_ATTEMPTS must be positive")
	}
	if err := validateDatabase(cfg.Database); err != nil {
		return err
	}
	if cfg.ActiveMQ.URL == "" || cfg.ActiveMQ.Destination == "" {
		return errors.New("ACTIVEMQ_URL and ACTIVEMQ_DESTINATION are required")
	}
	return nil
}

func validateDatabase(database Database) error {
	if database.Host == "" {
		return errors.New("OCR_DB_HOST is required")
	}
	port, err := strconv.Atoi(database.Port)
	if err != nil || port < 1 || port > 65535 {
		return errors.New("OCR_DB_PORT must be a valid TCP port")
	}
	if database.User == "" {
		return errors.New("OCR_DB_USER is required")
	}
	if strings.TrimSpace(database.Password) == "" {
		return errors.New("OCR_DB_PASSWORD is required")
	}
	if database.Name == "" {
		return errors.New("OCR_DB_NAME is required")
	}
	return nil
}

func parseDuration(getenv func(string) string, key string) (time.Duration, error) {
	raw := strings.TrimSpace(getenv(key))
	if raw == "" {
		return 0, fmt.Errorf("%s is required", key)
	}
	d, err := time.ParseDuration(raw)
	if err != nil {
		return 0, fmt.Errorf("%s invalid: %w", key, err)
	}
	return d, nil
}
