package config

import (
	"strings"
	"testing"
)

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func validEnv() map[string]string {
	return map[string]string{
		"REDIS_HOST": "redis", "REDIS_PORT": "6379", "REDIS_PASSWORD": "pw",
		"MESSAGING_STREAM_PREFIX": "foi", "MESSAGING_CONSUMER_GROUP": "foi-ocr",
		"OCR_CONSUMER_NAME":        "ocr-1",
		"MESSAGING_CLAIM_INTERVAL": "30s", "MESSAGING_CLAIM_MIN_IDLE": "20m",
		"MESSAGING_MAX_DELIVERY_ATTEMPTS": "5", "MESSAGING_SHUTDOWN_TIMEOUT": "30s",
		"OCR_PROCESSING_TIMEOUT": "10m",
		"OCR_DB_HOST":            "db", "OCR_DB_PORT": "5432", "OCR_DB_USER": "u", "OCR_DB_PASSWORD": "p", "OCR_DB_NAME": "ocr",
		"ACTIVEMQ_URL": "http://mq", "ACTIVEMQ_USERNAME": "mq", "ACTIVEMQ_PASSWORD": "mq", "ACTIVEMQ_DESTINATION": "foidococr",
	}
}

func TestLoadValid(t *testing.T) {
	cfg, err := Load(env(validEnv()))
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if cfg.Messaging.RedisAddress != "redis:6379" {
		t.Fatalf("RedisAddress = %q", cfg.Messaging.RedisAddress)
	}
	if cfg.Messaging.ConsumerName != "ocr-1" {
		t.Fatalf("ConsumerName = %q", cfg.Messaging.ConsumerName)
	}
}

func TestLoadRejectsClaimMinIdleNotExceedingProcessingTimeout(t *testing.T) {
	m := validEnv()
	m["MESSAGING_CLAIM_MIN_IDLE"] = "10m"
	m["OCR_PROCESSING_TIMEOUT"] = "10m"
	if _, err := Load(env(m)); err == nil {
		t.Fatal("expected error when claim min idle does not exceed processing timeout")
	}
}

func TestLoadRejectsWrongPrefix(t *testing.T) {
	m := validEnv()
	m["MESSAGING_STREAM_PREFIX"] = "wrong"
	if _, err := Load(env(m)); err == nil {
		t.Fatal("expected error for non-foi stream prefix")
	}
}

func TestLoadRejectsPartialRedisConfig(t *testing.T) {
	tests := []struct {
		name    string
		hostVal string
		portVal string
	}{
		{"empty REDIS_HOST", "", "6379"},
		{"empty REDIS_PORT", "redis", ""},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			m := validEnv()
			m["REDIS_HOST"] = tc.hostVal
			m["REDIS_PORT"] = tc.portVal
			if _, err := Load(env(m)); err == nil {
				t.Fatalf("expected error for host=%q port=%q", tc.hostVal, tc.portVal)
			}
		})
	}
}

func TestLoadRejectsInvalidDatabaseConfig(t *testing.T) {
	tests := []struct {
		name    string
		key     string
		value   string
		wantKey string
	}{
		{name: "empty host", key: "OCR_DB_HOST", wantKey: "OCR_DB_HOST"},
		{name: "empty port", key: "OCR_DB_PORT", wantKey: "OCR_DB_PORT"},
		{name: "non-numeric port", key: "OCR_DB_PORT", value: "postgres", wantKey: "OCR_DB_PORT"},
		{name: "zero port", key: "OCR_DB_PORT", value: "0", wantKey: "OCR_DB_PORT"},
		{name: "port above maximum", key: "OCR_DB_PORT", value: "65536", wantKey: "OCR_DB_PORT"},
		{name: "empty user", key: "OCR_DB_USER", wantKey: "OCR_DB_USER"},
		{name: "empty password", key: "OCR_DB_PASSWORD", wantKey: "OCR_DB_PASSWORD"},
		{name: "whitespace password", key: "OCR_DB_PASSWORD", value: " \t ", wantKey: "OCR_DB_PASSWORD"},
		{name: "empty name", key: "OCR_DB_NAME", wantKey: "OCR_DB_NAME"},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			m := validEnv()
			m[tc.key] = tc.value

			_, err := Load(env(m))
			if err == nil {
				t.Fatalf("Load() error = nil, want error containing %q", tc.wantKey)
			}
			if !strings.Contains(err.Error(), tc.wantKey) {
				t.Fatalf("Load() error = %q, want error containing %q", err, tc.wantKey)
			}
		})
	}
}

func TestLoadPreservesDatabasePasswordWhitespace(t *testing.T) {
	m := validEnv()
	m["OCR_DB_PASSWORD"] = " password with spaces "

	cfg, err := Load(env(m))
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if cfg.Database.Password != m["OCR_DB_PASSWORD"] {
		t.Fatalf("Database.Password = %q, want %q", cfg.Database.Password, m["OCR_DB_PASSWORD"])
	}
}
