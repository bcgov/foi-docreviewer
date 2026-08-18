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

type compressionPayload struct {
	JobID                    int            `json:"jobid"`
	S3FilePath               string         `json:"s3filepath"`
	Filename                 string         `json:"filename"`
	MinistryRequestID        int            `json:"ministryrequestid"`
	DocumentMasterID         int            `json:"documentmasterid"`
	Trigger                  string         `json:"trigger"`
	CreatedBy                string         `json:"createdby"`
	RequestNumber            string         `json:"requestnumber"`
	Batch                    string         `json:"batch"`
	Incompatible             bool           `json:"incompatible"`
	UserToken                *string        `json:"usertoken,omitempty"`
	BCGovCode                string         `json:"bcgovcode"`
	Attributes               map[string]any `json:"attributes"`
	DocumentID               *int           `json:"documentid,omitempty"`
	OutputDocumentMasterID   *int           `json:"outputdocumentmasterid,omitempty"`
	OriginalDocumentMasterID *int           `json:"originaldocumentmasterid,omitempty"`
}

type report struct {
	Acknowledged             bool            `json:"acknowledged"`
	Attributes               *map[string]any `json:"attributes,omitempty"`
	Dispatched               bool            `json:"dispatched"`
	DocumentMasterID         *int            `json:"document_master_id,omitempty"`
	DocumentID               *int            `json:"document_id,omitempty"`
	EventID                  string          `json:"event_id,omitempty"`
	Filename                 string          `json:"filename,omitempty"`
	Incompatible             *bool           `json:"incompatible,omitempty"`
	JobID                    *int            `json:"job_id,omitempty"`
	MinistryRequestID        *int            `json:"ministry_request_id,omitempty"`
	OutputDocumentMasterID   *int            `json:"output_document_master_id,omitempty"`
	OriginalDocumentMasterID *int            `json:"original_document_master_id,omitempty"`
	S3FilePath               string          `json:"s3_file_path,omitempty"`
	RequestNumber            string          `json:"request_number,omitempty"`
	Batch                    string          `json:"batch,omitempty"`
	Trigger                  string          `json:"trigger,omitempty"`
	CreatedBy                string          `json:"created_by,omitempty"`
	BCGovCode                string          `json:"bcgov_code,omitempty"`
	Topic                    string          `json:"topic"`
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
		documentID := env.Payload.DocumentID
		incompatible := env.Payload.Incompatible
		attributes := env.Payload.Attributes
		ministryRequestID := env.Payload.MinistryRequestID
		outputDocumentMasterID := env.Payload.OutputDocumentMasterID
		originalDocumentMasterID := env.Payload.OriginalDocumentMasterID
		h.report <- report{
			Acknowledged:             true,
			Attributes:               &attributes,
			Dispatched:               true,
			DocumentMasterID:         &documentMasterID,
			DocumentID:               documentID,
			EventID:                  env.EventID,
			Filename:                 env.Payload.Filename,
			Incompatible:             &incompatible,
			JobID:                    &jobID,
			MinistryRequestID:        &ministryRequestID,
			OutputDocumentMasterID:   outputDocumentMasterID,
			OriginalDocumentMasterID: originalDocumentMasterID,
			S3FilePath:               env.Payload.S3FilePath,
			RequestNumber:            env.Payload.RequestNumber,
			Batch:                    env.Payload.Batch,
			Trigger:                  env.Payload.Trigger,
			CreatedBy:                env.Payload.CreatedBy,
			BCGovCode:                env.Payload.BCGovCode,
			Topic:                    h.topic,
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
