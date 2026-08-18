// Command go-consumer is a test-only typed consumer for the Python compression
// producer contract. It is intentionally not used by a production service.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sync"
	"time"

	messaging "github.com/bcgov/foi-messaging-go"
)

type compressionDetails struct {
	Classification string `json:"classification"`
}

type compressionAttributes struct {
	Pages   int                `json:"pages"`
	Details compressionDetails `json:"details"`
}

type compressionPayload struct {
	JobID            int                   `json:"jobid"`
	DocumentMasterID int                   `json:"documentmasterid"`
	Filename         string                `json:"filename"`
	Incompatible     bool                  `json:"incompatible"`
	Attributes       compressionAttributes `json:"attributes"`
}

type report struct {
	Acknowledged     bool                   `json:"acknowledged"`
	Attributes       *compressionAttributes `json:"attributes,omitempty"`
	Dispatched       bool                   `json:"dispatched"`
	DocumentMasterID *int                   `json:"document_master_id,omitempty"`
	EventID          string                 `json:"event_id,omitempty"`
	Filename         string                 `json:"filename,omitempty"`
	Incompatible     *bool                  `json:"incompatible,omitempty"`
	JobID            *int                   `json:"job_id,omitempty"`
	Topic            string                 `json:"topic"`
}

type contractHandler struct {
	cancel context.CancelFunc
	once   sync.Once
	report chan<- report
	topic  string
}

func (h *contractHandler) Handle(_ context.Context, env messaging.Envelope[compressionPayload]) error {
	h.once.Do(func() {
		jobID := env.Payload.JobID
		documentMasterID := env.Payload.DocumentMasterID
		incompatible := env.Payload.Incompatible
		attributes := env.Payload.Attributes
		h.report <- report{
			Acknowledged:     true,
			Attributes:       &attributes,
			Dispatched:       true,
			DocumentMasterID: &documentMasterID,
			EventID:          env.EventID,
			Filename:         env.Payload.Filename,
			Incompatible:     &incompatible,
			JobID:            &jobID,
			Topic:            h.topic,
		}
		h.cancel()
	})
	return nil
}

func main() {
	topic := flag.String("topic", "", "logical Redis Streams topic to consume")
	group := flag.String("group", "", "Redis consumer group name")
	expectDispatch := flag.Bool("expect-dispatch", true, "whether a typed handler should run")
	timeout := flag.Duration("timeout", 2*time.Second, "maximum wait for the fixture result")
	flag.Parse()

	if *topic == "" {
		fail("-topic is required")
	}
	if *group == "" {
		*group = "contract-" + *topic
	}
	if os.Getenv("REDIS_ADDRESS") == "" {
		fail("REDIS_ADDRESS is required")
	}

	ctx, cancel := context.WithTimeout(context.Background(), *timeout)
	defer cancel()

	consumer, err := messaging.NewConsumer(messaging.Config{
		Source: "foi-docreviewer.compression-contract",
		Redis: messaging.RedisConfig{
			Address: os.Getenv("REDIS_ADDRESS"),
		},
		Consumer: messaging.ConsumerConfig{
			Group:           *group,
			ClaimInterval:   time.Second,
			ClaimMinIdle:    time.Second,
			ShutdownTimeout: 5 * time.Second,
		},
	})
	if err != nil {
		fail("creating consumer: %v", err)
	}
	defer func() {
		if err := consumer.Close(); err != nil {
			fail("closing consumer: %v", err)
		}
	}()

	reports := make(chan report, 1)
	definition := messaging.EventDef{
		Topic:   *topic,
		Type:    "document.compression.requested",
		Version: "1.0.0",
	}
	if err := messaging.RegisterHandler(
		consumer, definition, &contractHandler{cancel: cancel, report: reports, topic: *topic},
	); err != nil {
		fail("registering typed handler: %v", err)
	}

	if err := consumer.Run(ctx); err != nil {
		fail("running consumer: %v", err)
	}

	select {
	case result := <-reports:
		if !*expectDispatch {
			fail("typed handler dispatched an entry that should be rejected")
		}
		writeReport(result)
	default:
		if *expectDispatch {
			fail("typed handler did not receive an event before the timeout")
		}
		writeReport(report{Acknowledged: true, Dispatched: false, Topic: *topic})
	}
}

func writeReport(value report) {
	encoded, err := json.Marshal(value)
	if err != nil {
		fail("encoding report: %v", err)
	}
	fmt.Println(string(encoded))
}

func fail(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
	os.Exit(1)
}
