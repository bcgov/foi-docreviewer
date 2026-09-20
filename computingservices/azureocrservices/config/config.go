// Package config reads every tunable of the worker through utils.ViperEnvVariable
// and falls back to defaults that reproduce the pre-pipeline behaviour, so an
// unchanged .env keeps working. A bad value is logged (CONFIG_DEFAULT) and
// replaced by the default; loading never fails.
package config

import (
	"strconv"
	"time"

	"azureocrservice/logx"
	"azureocrservice/utils"
)

type Config struct {
	BatchSize, MaxConcurrentJobs, UploadConcurrency                      int
	AnalyzeRatePerSec                                                    float64
	PollInterval                                                         time.Duration
	PollMaxAttempts, MaxRetries                                          int
	RetryBase, RetryMax, JobTimeout                                      time.Duration
	AzureHTTPTimeout, S3HTTPTimeout, ReviewerTimeout, ActiveMQHTTPTimeout time.Duration
	UseBase64Source                                                      bool
	RunLockPath, LogFilePath                                             string
}

// Load reads the process environment / .env through viper.
func Load() Config { return LoadFrom(utils.ViperEnvVariable) }

// LoadFrom reads every key with get; tests pass a map-backed getter.
func LoadFrom(get func(string) string) Config {
	var cfg Config
	cfg.BatchSize = intKey(get, "activemqbatchsize", 0, 0)
	cfg.MaxConcurrentJobs = intKey(get, "maxconcurrentocrjobs", 1, 1)
	cfg.UploadConcurrency = intKey(get, "ocruploadconcurrency", 1, 1)
	cfg.AnalyzeRatePerSec = floatKey(get, "azureanalyzeratelimit", 0)
	cfg.PollInterval = secondsKey(get, "azurepollintervalseconds", 5)
	cfg.PollMaxAttempts = intKey(get, "azurepollmaxattempts", 120, 1)
	cfg.MaxRetries = intKey(get, "azuremaxretries", 0, 0)
	cfg.RetryBase = secondsKey(get, "azureretrybaseseconds", 2)
	cfg.RetryMax = secondsKey(get, "azureretrymaxseconds", 60)
	cfg.JobTimeout = secondsKey(get, "ocrjobtimeoutseconds", 900)
	cfg.AzureHTTPTimeout = secondsKey(get, "azurehttptimeoutseconds", 120)
	cfg.S3HTTPTimeout = secondsKey(get, "s3httptimeoutseconds", 120)
	cfg.ReviewerTimeout = secondsKey(get, "reviewerapitimeoutseconds", 30)
	cfg.ActiveMQHTTPTimeout = secondsKey(get, "activemqhttptimeoutseconds", 30)
	cfg.UseBase64Source = boolKey(get, "azureusebase64source", true)
	cfg.LogFilePath = get("logfilepath")
	cfg.RunLockPath = get("runlockpath")
	if cfg.RunLockPath == "" {
		cfg.RunLockPath = cfg.LogFilePath + "azureocrservice.lock"
	}
	return cfg
}

func useDefault(key, value, reason string) {
	logx.Event("CONFIG_DEFAULT", "key", key, "value", value, "reason", reason)
}

// intKey parses an integer >= min; empty → def.
func intKey(get func(string) string, key string, def, min int) int {
	raw := get(key)
	if raw == "" {
		return def
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		useDefault(key, raw, "not an integer")
		return def
	}
	if n < min {
		useDefault(key, raw, "below minimum "+strconv.Itoa(min))
		return def
	}
	return n
}

// floatKey parses a float >= 0; empty → def.
func floatKey(get func(string) string, key string, def float64) float64 {
	raw := get(key)
	if raw == "" {
		return def
	}
	f, err := strconv.ParseFloat(raw, 64)
	if err != nil || f < 0 {
		useDefault(key, raw, "not a non-negative number")
		return def
	}
	return f
}

// secondsKey parses a positive integer number of seconds; empty → def seconds.
func secondsKey(get func(string) string, key string, def int) time.Duration {
	raw := get(key)
	if raw == "" {
		return time.Duration(def) * time.Second
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n <= 0 {
		useDefault(key, raw, "not a positive integer")
		return time.Duration(def) * time.Second
	}
	return time.Duration(n) * time.Second
}

func boolKey(get func(string) string, key string, def bool) bool {
	raw := get(key)
	if raw == "" {
		return def
	}
	b, err := strconv.ParseBool(raw)
	if err != nil {
		useDefault(key, raw, "not a boolean")
		return def
	}
	return b
}
