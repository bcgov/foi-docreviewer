package config

import (
	"bytes"
	"strings"
	"testing"
	"time"

	"azureocrservice/logx"
)

func getter(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestLoadFromDefaults(t *testing.T) {
	cfg := LoadFrom(getter(map[string]string{"logfilepath": "/var/log/ocr/"}))
	if cfg.BatchSize != 0 || cfg.MaxConcurrentJobs != 1 || cfg.UploadConcurrency != 1 {
		t.Fatalf("batch defaults wrong: %+v", cfg)
	}
	if cfg.AnalyzeRatePerSec != 0 || cfg.PollInterval != 5*time.Second || cfg.PollMaxAttempts != 120 {
		t.Fatalf("azure defaults wrong: %+v", cfg)
	}
	if cfg.MaxRetries != 0 || cfg.RetryBase != 2*time.Second || cfg.RetryMax != 60*time.Second {
		t.Fatalf("retry defaults wrong: %+v", cfg)
	}
	if cfg.JobTimeout != 900*time.Second || cfg.AzureHTTPTimeout != 120*time.Second ||
		cfg.S3HTTPTimeout != 120*time.Second || cfg.ReviewerTimeout != 30*time.Second ||
		cfg.ActiveMQHTTPTimeout != 30*time.Second {
		t.Fatalf("timeout defaults wrong: %+v", cfg)
	}
	if !cfg.UseBase64Source {
		t.Fatal("UseBase64Source should default to true")
	}
	if cfg.RunLockPath != "/var/log/ocr/azureocrservice.lock" {
		t.Fatalf("RunLockPath = %q", cfg.RunLockPath)
	}
}

func TestLoadFromValues(t *testing.T) {
	cfg := LoadFrom(getter(map[string]string{
		"activemqbatchsize": "20", "maxconcurrentocrjobs": "5", "ocruploadconcurrency": "3",
		"azureanalyzeratelimit": "2.5", "azurepollintervalseconds": "7", "azurepollmaxattempts": "10",
		"azuremaxretries": "4", "azureretrybaseseconds": "1", "azureretrymaxseconds": "30",
		"ocrjobtimeoutseconds": "60", "azurehttptimeoutseconds": "15", "s3httptimeoutseconds": "16",
		"reviewerapitimeoutseconds": "17", "activemqhttptimeoutseconds": "18",
		"azureusebase64source": "false", "runlockpath": "C:\\ocr\\run.lock",
	}))
	if cfg.BatchSize != 20 || cfg.MaxConcurrentJobs != 5 || cfg.UploadConcurrency != 3 || cfg.AnalyzeRatePerSec != 2.5 {
		t.Fatalf("%+v", cfg)
	}
	if cfg.PollInterval != 7*time.Second || cfg.PollMaxAttempts != 10 || cfg.MaxRetries != 4 ||
		cfg.RetryBase != time.Second || cfg.RetryMax != 30*time.Second || cfg.JobTimeout != time.Minute {
		t.Fatalf("%+v", cfg)
	}
	if cfg.AzureHTTPTimeout != 15*time.Second || cfg.S3HTTPTimeout != 16*time.Second ||
		cfg.ReviewerTimeout != 17*time.Second || cfg.ActiveMQHTTPTimeout != 18*time.Second {
		t.Fatalf("%+v", cfg)
	}
	if cfg.UseBase64Source || cfg.RunLockPath != "C:\\ocr\\run.lock" {
		t.Fatalf("%+v", cfg)
	}
}

func TestLoadFromBadValueFallsBackAndLogs(t *testing.T) {
	var buf bytes.Buffer
	logx.Output = &buf
	defer func() { logx.Output = nil }()
	cfg := LoadFrom(getter(map[string]string{
		"maxconcurrentocrjobs": "zero", "azurepollintervalseconds": "0", "ocruploadconcurrency": "-1",
	}))
	if cfg.MaxConcurrentJobs != 1 || cfg.PollInterval != 5*time.Second || cfg.UploadConcurrency != 1 {
		t.Fatalf("expected defaults, got %+v", cfg)
	}
	out := buf.String()
	for _, key := range []string{"maxconcurrentocrjobs", "azurepollintervalseconds", "ocruploadconcurrency"} {
		if !strings.Contains(out, "CONFIG_DEFAULT key="+key) {
			t.Fatalf("missing CONFIG_DEFAULT for %s in %q", key, out)
		}
	}
}
