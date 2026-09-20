package logx

import (
	"bytes"
	"errors"
	"testing"
	"time"
)

func TestEventFormatsKeyValues(t *testing.T) {
	var buf bytes.Buffer
	Output = &buf
	defer func() { Output = nil }()

	Event("JOB_FAILED", "documentid", int64(456), "stage", "poll", "reason", "rate limit hit",
		"err", errors.New("boom"), "took", 1500*time.Millisecond, "ok", true)

	want := `JOB_FAILED documentid=456 stage=poll reason="rate limit hit" err=boom took=1.5s ok=true` + "\n"
	if buf.String() != want {
		t.Fatalf("got %q\nwant %q", buf.String(), want)
	}
}

func TestEventOddKvIsTolerated(t *testing.T) {
	var buf bytes.Buffer
	Output = &buf
	defer func() { Output = nil }()
	Event("RUN_START", "batchsize")
	if buf.String() != "RUN_START batchsize=<missing>\n" {
		t.Fatalf("got %q", buf.String())
	}
}
