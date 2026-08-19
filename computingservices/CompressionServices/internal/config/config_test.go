package config

import (
	"math"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestLoadStandardNormal(t *testing.T) {
	env := standardNormalEnv()

	got, err := Load(func(key string) string { return env[key] })

	require.NoError(t, err)
	assert.Equal(t, ModeStandard, got.Mode)
	assert.Equal(t, WorkloadNormal, got.Workload)
	assert.Equal(t, 15*time.Minute, got.ProcessingTimeout)
	assert.Equal(t, "redis:6379", got.Messaging.RedisAddress)
	assert.Equal(t, 30*time.Second, got.Messaging.ClaimInterval)
	assert.Equal(t, 17*time.Minute, got.Messaging.ClaimMinIdle)
	assert.Equal(t, 5, got.Messaging.MaxDeliveryAttempts)
	assert.Equal(t, 25*time.Second, got.Messaging.ShutdownTimeout)
	assert.Equal(t, 20*time.Minute, got.Reconciliation.NormalAfter)
	assert.Equal(t, 75*time.Minute, got.Reconciliation.LargeAfter)
	assert.Equal(t, 75*time.Minute, got.Reconciliation.UnknownAfter)
	assert.Equal(t, 100, got.Reconciliation.BatchSize)
	assert.Equal(t, 15*time.Minute, got.S3.PresignExpiry)
}

func TestLoadValidatesPresignExpirySecurityMaximum(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    time.Duration
		wantErr bool
	}{
		{name: "defaults to fifteen minutes", want: 15 * time.Minute},
		{name: "accepts shorter positive expiry", value: "5m", want: 5 * time.Minute},
		{name: "accepts fifteen minute maximum", value: "15m", want: 15 * time.Minute},
		{name: "rejects zero", value: "0s", wantErr: true},
		{name: "rejects negative", value: "-1s", wantErr: true},
		{name: "rejects above maximum", value: "15m1ns", wantErr: true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			env := standardNormalEnv()
			env["COMPRESSION_S3_PRESIGN_EXPIRY"] = test.value

			got, err := Load(func(key string) string { return env[key] })

			if test.wantErr {
				require.Error(t, err)
				assert.Contains(t, err.Error(), "COMPRESSION_S3_PRESIGN_EXPIRY")
				return
			}
			require.NoError(t, err)
			assert.Equal(t, test.want, got.S3.PresignExpiry)
		})
	}
}

func TestLoadValidatesCompressionRatioBusinessRange(t *testing.T) {
	tests := []struct {
		name    string
		value   string
		want    float64
		wantErr bool
	}{
		{name: "accepts lower positive value", value: "0.01", want: 0.01},
		{name: "accepts upper boundary", value: "1", want: 1},
		{name: "rejects zero", value: "0", wantErr: true},
		{name: "rejects negative", value: "-0.1", wantErr: true},
		{name: "rejects above one", value: "1.0001", wantErr: true},
		{name: "rejects NaN", value: "NaN", wantErr: true},
		{name: "rejects positive infinity", value: "+Inf", wantErr: true},
		{name: "rejects negative infinity", value: "-Inf", wantErr: true},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			env := standardNormalEnv()
			env["COMPRESSION_RATIO_THRESHOLD"] = test.value

			got, err := Load(func(key string) string { return env[key] })

			if test.wantErr {
				require.Error(t, err)
				assert.Contains(t, err.Error(), "COMPRESSION_RATIO_THRESHOLD")
				return
			}
			require.NoError(t, err)
			assert.InDelta(t, test.want, got.CompressionRatioThreshold, math.SmallestNonzeroFloat64)
		})
	}
}

func TestLoadUsesLargeWorkloadDurationDefaults(t *testing.T) {
	env := standardNormalEnv()
	env["COMPRESSION_WORKLOAD"] = "large"
	env["MESSAGING_CONSUMER_GROUP"] = "compression-large"

	got, err := Load(func(key string) string { return env[key] })

	require.NoError(t, err)
	assert.Equal(t, 60*time.Minute, got.ProcessingTimeout)
	assert.Equal(t, 62*time.Minute, got.Messaging.ClaimMinIdle)
}

func TestLoadRejectsInvalidConfiguration(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(map[string]string)
		wantKey string
	}{
		{
			name: "invalid mode",
			mutate: func(env map[string]string) {
				env["COMPRESSION_MESSAGING_MODE"] = "dual"
			},
			wantKey: "COMPRESSION_MESSAGING_MODE",
		},
		{
			name: "invalid workload",
			mutate: func(env map[string]string) {
				env["COMPRESSION_WORKLOAD"] = "historical"
			},
			wantKey: "COMPRESSION_WORKLOAD",
		},
		{
			name: "standard mode requires topic",
			mutate: func(env map[string]string) {
				env["COMPRESSION_TOPIC"] = ""
			},
			wantKey: "COMPRESSION_TOPIC",
		},
		{
			name: "standard mode requires consumer group",
			mutate: func(env map[string]string) {
				env["MESSAGING_CONSUMER_GROUP"] = ""
			},
			wantKey: "MESSAGING_CONSUMER_GROUP",
		},
		{
			name: "legacy mode requires stream key",
			mutate: func(env map[string]string) {
				env["COMPRESSION_MESSAGING_MODE"] = "legacy"
			},
			wantKey: "COMPRESSION_STREAM_KEY",
		},
		{
			name: "legacy mode requires checkpoint key",
			mutate: func(env map[string]string) {
				env["COMPRESSION_MESSAGING_MODE"] = "legacy"
				env["COMPRESSION_STREAM_KEY"] = "legacy-compression"
			},
			wantKey: "COMPRESSION_CHECKPOINT_KEY",
		},
		{
			name: "rejects invalid processing timeout",
			mutate: func(env map[string]string) {
				env["COMPRESSION_PROCESSING_TIMEOUT"] = "later"
			},
			wantKey: "COMPRESSION_PROCESSING_TIMEOUT",
		},
		{
			name: "claim idle must exceed processing timeout",
			mutate: func(env map[string]string) {
				env["MESSAGING_CLAIM_MIN_IDLE"] = "15m"
			},
			wantKey: "MESSAGING_CLAIM_MIN_IDLE",
		},
		{
			name: "reconciliation threshold must exceed claim idle",
			mutate: func(env map[string]string) {
				env["COMPRESSION_RECONCILIATION_NORMAL_AFTER"] = "17m"
			},
			wantKey: "COMPRESSION_RECONCILIATION_NORMAL_AFTER",
		},
		{
			name: "rejects malformed redis port",
			mutate: func(env map[string]string) {
				env["REDIS_PORT"] = "redis"
			},
			wantKey: "REDIS_PORT",
		},
		{
			name: "rejects malformed database port",
			mutate: func(env map[string]string) {
				env["COMPRESSION_DB_PORT"] = "postgres"
			},
			wantKey: "COMPRESSION_DB_PORT",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := standardNormalEnv()
			tt.mutate(env)

			_, err := Load(func(key string) string { return env[key] })

			require.Error(t, err)
			assert.Contains(t, err.Error(), tt.wantKey)
			assert.NotContains(t, err.Error(), "secret")
		})
	}
}

func TestLoadRejectsUnsafeReconciliationThresholds(t *testing.T) {
	tests := []struct {
		name    string
		mutate  func(map[string]string)
		wantKey string
	}{
		{
			name: "normal threshold uses normal claim budget",
			mutate: func(env map[string]string) {
				env["COMPRESSION_RECONCILIATION_NORMAL_AFTER"] = "17m"
			},
			wantKey: "COMPRESSION_RECONCILIATION_NORMAL_AFTER",
		},
		{
			name: "large threshold uses large claim budget",
			mutate: func(env map[string]string) {
				env["COMPRESSION_RECONCILIATION_LARGE_AFTER"] = "62m"
			},
			wantKey: "COMPRESSION_RECONCILIATION_LARGE_AFTER",
		},
		{
			name: "unknown threshold uses conservative large claim budget",
			mutate: func(env map[string]string) {
				env["COMPRESSION_RECONCILIATION_UNKNOWN_AFTER"] = "62m"
			},
			wantKey: "COMPRESSION_RECONCILIATION_UNKNOWN_AFTER",
		},
		{
			name: "normal threshold remains safe in a large workload configuration",
			mutate: func(env map[string]string) {
				env["COMPRESSION_WORKLOAD"] = "large"
				env["MESSAGING_CONSUMER_GROUP"] = "compression-large"
				env["COMPRESSION_RECONCILIATION_NORMAL_AFTER"] = "17m"
			},
			wantKey: "COMPRESSION_RECONCILIATION_NORMAL_AFTER",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := standardNormalEnv()
			tt.mutate(env)

			_, err := Load(func(key string) string { return env[key] })

			require.Error(t, err)
			assert.Contains(t, err.Error(), tt.wantKey)
		})
	}
}

func TestLoadValidatesTCPPortBoundaries(t *testing.T) {
	tests := []struct {
		name    string
		key     string
		value   string
		wantErr bool
	}{
		{name: "redis zero", key: "REDIS_PORT", value: "0", wantErr: true},
		{name: "redis maximum", key: "REDIS_PORT", value: "65535"},
		{name: "redis above maximum", key: "REDIS_PORT", value: "65536", wantErr: true},
		{name: "database zero", key: "COMPRESSION_DB_PORT", value: "0", wantErr: true},
		{name: "database maximum", key: "COMPRESSION_DB_PORT", value: "65535"},
		{name: "database above maximum", key: "COMPRESSION_DB_PORT", value: "65536", wantErr: true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			env := standardNormalEnv()
			env[tt.key] = tt.value

			_, err := Load(func(key string) string { return env[key] })

			if tt.wantErr {
				require.Error(t, err)
				assert.Contains(t, err.Error(), tt.key)
				return
			}
			require.NoError(t, err)
		})
	}
}

func TestLoadPreservesPasswordWhitespace(t *testing.T) {
	t.Run("preserves non-empty password whitespace", func(t *testing.T) {
		env := standardNormalEnv()
		env["REDIS_PASSWORD"] = " redis secret "
		env["COMPRESSION_DB_PASSWORD"] = " database secret "

		got, err := Load(func(key string) string { return env[key] })

		require.NoError(t, err)
		assert.Equal(t, " redis secret ", got.Messaging.RedisPassword)
		assert.Equal(t, " database secret ", got.Database.Password)
	})

	t.Run("rejects whitespace-only database password", func(t *testing.T) {
		env := standardNormalEnv()
		env["COMPRESSION_DB_PASSWORD"] = " \t "

		_, err := Load(func(key string) string { return env[key] })

		require.Error(t, err)
		assert.Contains(t, err.Error(), "COMPRESSION_DB_PASSWORD")
		assert.NotContains(t, err.Error(), env["COMPRESSION_DB_PASSWORD"])
	})
}

func standardNormalEnv() map[string]string {
	return map[string]string{
		"COMPRESSION_MESSAGING_MODE": "standard",
		"COMPRESSION_WORKLOAD":       "normal",
		"REDIS_HOST":                 "redis",
		"REDIS_PORT":                 "6379",
		"MESSAGING_STREAM_PREFIX":    "foi",
		"COMPRESSION_TOPIC":          "compression",
		"MESSAGING_CONSUMER_GROUP":   "compression-normal",
		"COMPRESSION_DB_HOST":        "db",
		"COMPRESSION_DB_PORT":        "5432",
		"COMPRESSION_DB_NAME":        "reviewer",
		"COMPRESSION_DB_USER":        "reviewer",
		"COMPRESSION_DB_PASSWORD":    "secret",
		"COMPRESSION_S3_HOST":        "https://s3.example",
		"COMPRESSION_S3_REGION":      "ca-central-1",
		"COMPRESSION_S3_ENV":         "test",
	}
}

func TestLoadErrorsDoNotExposeSecretValues(t *testing.T) {
	env := standardNormalEnv()
	env["REDIS_PASSWORD"] = "redis-secret"
	env["COMPRESSION_DB_PASSWORD"] = "database-secret"
	env["COMPRESSION_PROCESSING_TIMEOUT"] = "invalid"

	_, err := Load(func(key string) string { return env[key] })

	require.Error(t, err)
	assert.False(t, strings.Contains(err.Error(), "redis-secret"))
	assert.False(t, strings.Contains(err.Error(), "database-secret"))
}
