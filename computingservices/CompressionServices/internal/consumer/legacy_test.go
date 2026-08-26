package consumer

import (
	"context"
	"errors"
	"math"
	"strings"
	"testing"
	"time"

	"compressionservices/internal/compression"
	"compressionservices/internal/config"
	"compressionservices/internal/store"
	"compressionservices/models"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type fakeLegacyStream struct {
	lastID    string
	lastErr   error
	lastFunc  func(context.Context, string) (string, error)
	readFunc  func(context.Context, string, string) ([]LegacyMessage, error)
	saveFunc  func(context.Context, string, string) error
	lastKeys  []string
	readKeys  []string
	readAfter []string
	savedKeys []string
	savedIDs  []string
	lastCalls int
	readCalls int
	saveCalls int
}

func (s *fakeLegacyStream) LastID(ctx context.Context, checkpointKey string) (string, error) {
	s.lastCalls++
	s.lastKeys = append(s.lastKeys, checkpointKey)
	if s.lastFunc != nil {
		return s.lastFunc(ctx, checkpointKey)
	}
	return s.lastID, s.lastErr
}

func (s *fakeLegacyStream) ReadAfter(
	ctx context.Context,
	streamKey string,
	after string,
) ([]LegacyMessage, error) {
	s.readCalls++
	s.readKeys = append(s.readKeys, streamKey)
	s.readAfter = append(s.readAfter, after)
	if s.readFunc != nil {
		return s.readFunc(ctx, streamKey, after)
	}
	return nil, nil
}

func (s *fakeLegacyStream) SaveLastID(
	ctx context.Context,
	checkpointKey string,
	id string,
) error {
	s.saveCalls++
	s.savedKeys = append(s.savedKeys, checkpointKey)
	s.savedIDs = append(s.savedIDs, id)
	if s.saveFunc != nil {
		return s.saveFunc(ctx, checkpointKey, id)
	}
	s.lastID = id
	return nil
}

type fakeLegacyProcessor struct {
	process func(context.Context, compression.Delivery) error
}

func (p *fakeLegacyProcessor) Process(
	ctx context.Context,
	delivery compression.Delivery,
) error {
	if p.process != nil {
		return p.process(ctx, delivery)
	}
	return nil
}

type typedNilLegacyStream struct{}

func (*typedNilLegacyStream) LastID(context.Context, string) (string, error) {
	return "", nil
}

func (*typedNilLegacyStream) ReadAfter(
	context.Context,
	string,
	string,
) ([]LegacyMessage, error) {
	return nil, nil
}

func (*typedNilLegacyStream) SaveLastID(context.Context, string, string) error {
	return nil
}

func TestLegacyRunProcessesAndCheckpointsStrictlyInOrder(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	events := []string{}
	stream := &fakeLegacyStream{lastID: "0"}
	stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
		return []LegacyMessage{
			validLegacyMessage("1710000000000-0", 41),
			validLegacyMessage("1710000000001-0", 42),
		}, nil
	}
	stream.saveFunc = func(_ context.Context, _ string, id string) error {
		events = append(events, "save:"+id)
		stream.lastID = id
		if id == "1710000000001-0" {
			cancel()
		}
		return nil
	}
	processor := &fakeLegacyProcessor{process: func(
		_ context.Context,
		delivery compression.Delivery,
	) error {
		events = append(events, "process:"+delivery.StreamID)
		return nil
	}}

	err := NewLegacy(stream, processor, validLegacyOptions()).Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, []string{
		"process:1710000000000-0",
		"save:1710000000000-0",
		"process:1710000000001-0",
		"save:1710000000001-0",
	}, events)
	assert.Equal(t, []string{"1710000000000-0", "1710000000001-0"}, stream.savedIDs)
	assert.Equal(t, []string{"legacy:checkpoint", "legacy:checkpoint"}, stream.savedKeys)
}

func TestLegacyRunRetainsCurrentDeliveryAcrossRetryAndBacksOff(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	stream := &fakeLegacyStream{lastID: "0"}
	stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
		return []LegacyMessage{
			validLegacyMessage("1710000000000-0", 41),
			validLegacyMessage("1710000000001-0", 42),
		}, nil
	}
	stream.saveFunc = func(_ context.Context, _ string, id string) error {
		if id == "1710000000001-0" {
			cancel()
		}
		return nil
	}

	attempts := map[string]int{}
	processOrder := []string{}
	processor := &fakeLegacyProcessor{process: func(
		_ context.Context,
		delivery compression.Delivery,
	) error {
		attempts[delivery.StreamID]++
		processOrder = append(processOrder, delivery.StreamID)
		if delivery.StreamID == "1710000000000-0" && attempts[delivery.StreamID] <= 10 {
			return compression.NewRetryableFailure(
				store.FailureCodeDatabaseUnavailable,
				errors.New("transient database detail"),
			)
		}
		if delivery.StreamID == "1710000000001-0" && attempts[delivery.StreamID] == 1 {
			return compression.NewRetryableFailure(
				store.FailureCodeS3DownloadTimeout,
				errors.New("transient object detail"),
			)
		}
		return nil
	}}
	legacy := NewLegacy(stream, processor, validLegacyOptions())
	waits := []time.Duration{}
	legacy.wait = func(_ context.Context, duration time.Duration) error {
		waits = append(waits, duration)
		return nil
	}

	err := legacy.Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, []time.Duration{
		250 * time.Millisecond,
		500 * time.Millisecond,
		time.Second,
		2 * time.Second,
		4 * time.Second,
		8 * time.Second,
		16 * time.Second,
		30 * time.Second,
		30 * time.Second,
		30 * time.Second,
		250 * time.Millisecond,
	}, waits)
	assert.Equal(t, 11, attempts["1710000000000-0"])
	assert.Equal(t, 2, attempts["1710000000001-0"])
	require.Len(t, stream.savedIDs, 2)
	assert.Equal(t, "1710000000000-0", stream.savedIDs[0])
	assert.NotContains(t, processOrder[:11], "1710000000001-0")
}

func TestLegacyRunRetryCancellationInterruptsBackoffWithoutCheckpoint(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	stream := singleMessageLegacyStream(validLegacyMessage("1710000000000-0", 41))
	processor := &fakeLegacyProcessor{process: func(context.Context, compression.Delivery) error {
		return compression.NewRetryableFailure(
			store.FailureCodeDatabaseUnavailable,
			errors.New("temporary detail"),
		)
	}}
	legacy := NewLegacy(stream, processor, validLegacyOptions())
	waitCalls := 0
	legacy.wait = func(waitCtx context.Context, duration time.Duration) error {
		waitCalls++
		assert.Equal(t, 250*time.Millisecond, duration)
		cancel()
		return waitLegacyBackoff(waitCtx, duration)
	}

	err := legacy.Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, 1, waitCalls)
	assert.Zero(t, stream.saveCalls)
}

func TestLegacyRunSaveFailureStopsBeforeNextDelivery(t *testing.T) {
	saveCause := errors.New("password=save-secret")
	stream := &fakeLegacyStream{lastID: "0"}
	stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
		return []LegacyMessage{
			validLegacyMessage("1710000000000-0", 41),
			validLegacyMessage("1710000000001-0", 42),
		}, nil
	}
	stream.saveFunc = func(context.Context, string, string) error { return saveCause }
	processed := []int{}
	processor := &fakeLegacyProcessor{process: func(
		_ context.Context,
		delivery compression.Delivery,
	) error {
		processed = append(processed, delivery.Message.JobID)
		return nil
	}}

	err := NewLegacy(stream, processor, validLegacyOptions()).Run(context.Background())

	require.Error(t, err)
	assert.ErrorIs(t, err, saveCause)
	assert.NotContains(t, err.Error(), "save-secret")
	assert.Equal(t, []int{41}, processed)
	assert.Equal(t, []string{"1710000000000-0"}, stream.savedIDs)
}

func TestLegacyRunRestartReadsAfterDurableCheckpoint(t *testing.T) {
	stream := &fakeLegacyStream{}
	stream.readFunc = func(_ context.Context, _ string, after string) ([]LegacyMessage, error) {
		switch after {
		case "0":
			return []LegacyMessage{validLegacyMessage("1710000000000-0", 41)}, nil
		case "1710000000000-0":
			return []LegacyMessage{validLegacyMessage("1710000000001-0", 42)}, nil
		default:
			return nil, errors.New("unexpected cursor")
		}
	}
	var cancel context.CancelFunc
	stream.saveFunc = func(_ context.Context, _ string, id string) error {
		stream.lastID = id
		cancel()
		return nil
	}
	processed := []int{}
	processor := &fakeLegacyProcessor{process: func(
		_ context.Context,
		delivery compression.Delivery,
	) error {
		processed = append(processed, delivery.Message.JobID)
		return nil
	}}
	legacy := NewLegacy(stream, processor, validLegacyOptions())

	firstCtx, firstCancel := context.WithCancel(context.Background())
	cancel = firstCancel
	require.ErrorIs(t, legacy.Run(firstCtx), context.Canceled)
	firstCancel()

	secondCtx, secondCancel := context.WithCancel(context.Background())
	cancel = secondCancel
	require.ErrorIs(t, legacy.Run(secondCtx), context.Canceled)
	secondCancel()

	assert.Equal(t, []string{"0", "1710000000000-0"}, stream.readAfter)
	assert.Equal(t, []int{41, 42}, processed)
	assert.Equal(t, "1710000000001-0", stream.lastID)
}

func TestLegacyRunMalformedPayloadWithJobIDUsesHandlerBeforeCheckpoint(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	message := validLegacyMessage("1710000000000-0", 41)
	message.Values["attributes"] = `{"secret":"do-not-expose"`
	stream := singleMessageLegacyStream(message)
	stream.saveFunc = func(context.Context, string, string) error {
		cancel()
		return nil
	}
	repository := &terminalizingLegacyRepository{}
	handler := compression.NewHandler(
		repository,
		malformedLegacyCompressor{},
		nil,
		compression.Options{
			Workload:            config.WorkloadNormal,
			ProcessingTimeout:   time.Minute,
			FinalizationTimeout: time.Second,
			Now:                 time.Now,
		},
	)

	err := NewLegacy(stream, handler, validLegacyOptions()).Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	assert.Equal(t, 1, repository.failCalls)
	assert.Equal(t, 41, repository.failedJobID)
	assert.Equal(t, store.FailureCodeInvalidMessage, repository.failureCode)
	assert.Equal(t, []string{"1710000000000-0"}, stream.savedIDs)
}

func TestLegacyRunMissingOrInvalidJobIDReturnsSafeOperatorError(t *testing.T) {
	tests := []struct {
		name  string
		value any
		omit  bool
	}{
		{name: "missing", omit: true},
		{name: "blank", value: " "},
		{name: "not numeric", value: "secret-job-value"},
		{name: "zero", value: "0"},
		{name: "negative", value: "-4"},
		{name: "fractional", value: 4.5},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			message := validLegacyMessage("1710000000000-0", 41)
			message.Values["attributes"] = `{"token":"payload-secret"}`
			if tt.omit {
				delete(message.Values, "jobid")
			} else {
				message.Values["jobid"] = tt.value
			}
			stream := singleMessageLegacyStream(message)
			processCalls := 0
			processor := &fakeLegacyProcessor{process: func(
				context.Context,
				compression.Delivery,
			) error {
				processCalls++
				return nil
			}}

			err := NewLegacy(stream, processor, validLegacyOptions()).Run(context.Background())

			require.Error(t, err)
			assert.Contains(t, err.Error(), "legacy")
			assert.NotContains(t, err.Error(), "payload-secret")
			assert.NotContains(t, err.Error(), "secret-job-value")
			assert.Zero(t, processCalls)
			assert.Zero(t, stream.saveCalls)
		})
	}
}

func TestLegacyRunNonRetryableProcessorFailureDoesNotRetryOrCheckpoint(t *testing.T) {
	processorCause := errors.New("document detail at /secret/input.pdf")
	tests := []struct {
		name string
		err  error
	}{
		{
			name: "deterministic failure",
			err: compression.NewDeterministicFailure(
				store.FailureCodeUnsupportedDocument,
				processorCause,
			),
		},
		{name: "unclassified failure", err: processorCause},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stream := singleMessageLegacyStream(validLegacyMessage("1710000000000-0", 41))
			calls := 0
			processor := &fakeLegacyProcessor{process: func(
				context.Context,
				compression.Delivery,
			) error {
				calls++
				return tt.err
			}}
			legacy := NewLegacy(stream, processor, validLegacyOptions())
			legacy.wait = func(context.Context, time.Duration) error {
				t.Fatal("non-retryable error entered backoff")
				return nil
			}

			err := legacy.Run(context.Background())

			require.Error(t, err)
			assert.ErrorIs(t, err, processorCause)
			assert.NotContains(t, err.Error(), "secret")
			assert.Equal(t, 1, calls)
			assert.Zero(t, stream.saveCalls)
		})
	}
}

func TestLegacyRunValidatesLifecycleBoundaries(t *testing.T) {
	validStream := &fakeLegacyStream{}
	validProcessor := &fakeLegacyProcessor{}
	var typedNilStream *typedNilLegacyStream
	var typedNilProcessor *fakeLegacyProcessor

	tests := []struct {
		name      string
		legacy    *Legacy
		ctx       context.Context
		wantCause error
	}{
		{name: "nil receiver", legacy: nil, ctx: context.Background()},
		{
			name:   "nil stream",
			legacy: NewLegacy(nil, validProcessor, validLegacyOptions()),
			ctx:    context.Background(),
		},
		{
			name:   "typed nil stream",
			legacy: NewLegacy(typedNilStream, validProcessor, validLegacyOptions()),
			ctx:    context.Background(),
		},
		{
			name:   "nil processor",
			legacy: NewLegacy(validStream, nil, validLegacyOptions()),
			ctx:    context.Background(),
		},
		{
			name:   "typed nil processor",
			legacy: NewLegacy(validStream, typedNilProcessor, validLegacyOptions()),
			ctx:    context.Background(),
		},
		{
			name:   "nil context",
			legacy: NewLegacy(validStream, validProcessor, validLegacyOptions()),
			ctx:    nil,
		},
		{
			name:   "empty options",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{}),
			ctx:    context.Background(),
		},
		{
			name: "blank stream key",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{
				CheckpointKey: "legacy:checkpoint",
				StartID:       "0",
				Workload:      config.WorkloadNormal,
			}),
			ctx: context.Background(),
		},
		{
			name: "blank checkpoint key",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{
				StreamKey: "legacy:compression",
				StartID:   "0",
				Workload:  config.WorkloadNormal,
			}),
			ctx: context.Background(),
		},
		{
			name: "blank start identifier",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{
				StreamKey:     "legacy:compression",
				CheckpointKey: "legacy:checkpoint",
				Workload:      config.WorkloadNormal,
			}),
			ctx: context.Background(),
		},
		{
			name: "unsupported start identifier",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{
				StreamKey:     "legacy:compression",
				CheckpointKey: "legacy:checkpoint",
				StartID:       "1-0",
				Workload:      config.WorkloadNormal,
			}),
			ctx: context.Background(),
		},
		{
			name: "invalid workload",
			legacy: NewLegacy(validStream, validProcessor, LegacyOptions{
				StreamKey:     "legacy:compression",
				CheckpointKey: "legacy:checkpoint",
				StartID:       "0",
			}),
			ctx: context.Background(),
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := tt.legacy.Run(tt.ctx)
			require.Error(t, err)
			assert.NotContains(t, err.Error(), "secret")
		})
	}

	preCanceled, cancel := context.WithCancel(context.Background())
	cancel()
	stream := &fakeLegacyStream{}
	err := NewLegacy(stream, validProcessor, validLegacyOptions()).Run(preCanceled)
	require.ErrorIs(t, err, context.Canceled)
	assert.Zero(t, stream.lastCalls)
}

func TestLegacyRunUsesConfiguredStartWhenCheckpointIsBlank(t *testing.T) {
	readCause := errors.New("redis endpoint password=start-secret")
	stream := &fakeLegacyStream{lastID: " \t "}
	stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
		return nil, readCause
	}
	options := validLegacyOptions()
	options.StartID = "$"

	err := NewLegacy(stream, &fakeLegacyProcessor{}, options).Run(context.Background())

	require.Error(t, err)
	assert.ErrorIs(t, err, readCause)
	assert.Equal(t, []string{"$"}, stream.readAfter)
	assert.NotContains(t, err.Error(), "start-secret")
}

func TestLegacyRunPropagatesStreamFailuresSafely(t *testing.T) {
	tests := []struct {
		name        string
		configure   func(*fakeLegacyStream)
		wantRead    int
		wantProcess int
	}{
		{
			name: "last identifier",
			configure: func(stream *fakeLegacyStream) {
				stream.lastErr = errors.New("last-id password=do-not-expose")
			},
		},
		{
			name: "read",
			configure: func(stream *fakeLegacyStream) {
				stream.lastID = "0"
				stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
					return nil, errors.New("read password=do-not-expose")
				}
			},
			wantRead: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			stream := &fakeLegacyStream{}
			tt.configure(stream)
			processCalls := 0
			processor := &fakeLegacyProcessor{process: func(
				context.Context,
				compression.Delivery,
			) error {
				processCalls++
				return nil
			}}

			err := NewLegacy(stream, processor, validLegacyOptions()).Run(context.Background())

			require.Error(t, err)
			assert.NotContains(t, err.Error(), "do-not-expose")
			assert.Equal(t, tt.wantRead, stream.readCalls)
			assert.Equal(t, tt.wantProcess, processCalls)
			assert.Zero(t, stream.saveCalls)
		})
	}
}

func TestLegacyRunCancellationDuringReadReturnsContextCause(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	stream := &fakeLegacyStream{lastID: "0"}
	stream.readFunc = func(readCtx context.Context, _ string, _ string) ([]LegacyMessage, error) {
		cancel()
		<-readCtx.Done()
		return nil, readCtx.Err()
	}

	err := NewLegacy(stream, &fakeLegacyProcessor{}, validLegacyOptions()).Run(ctx)

	require.ErrorIs(t, err, context.Canceled)
	assert.Zero(t, stream.saveCalls)
}

func TestLegacyRunRejectsBlankMessageIDBeforeProcessing(t *testing.T) {
	stream := singleMessageLegacyStream(validLegacyMessage(" \t", 41))
	processCalls := 0
	processor := &fakeLegacyProcessor{process: func(
		context.Context,
		compression.Delivery,
	) error {
		processCalls++
		return nil
	}}

	err := NewLegacy(stream, processor, validLegacyOptions()).Run(context.Background())

	require.Error(t, err)
	assert.Zero(t, processCalls)
	assert.Zero(t, stream.saveCalls)
}

func TestLegacyRunRecoversDependencyPanicsWithoutLeakingDetails(t *testing.T) {
	panicCause := errors.New("panic password=do-not-expose")
	tests := []struct {
		name      string
		stream    *fakeLegacyStream
		processor *fakeLegacyProcessor
	}{
		{
			name: "stream panic",
			stream: &fakeLegacyStream{lastFunc: func(context.Context, string) (string, error) {
				panic(panicCause)
			}},
			processor: &fakeLegacyProcessor{},
		},
		{
			name:   "processor panic",
			stream: singleMessageLegacyStream(validLegacyMessage("1710000000000-0", 41)),
			processor: &fakeLegacyProcessor{process: func(
				context.Context,
				compression.Delivery,
			) error {
				panic(panicCause)
			}},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := NewLegacy(tt.stream, tt.processor, validLegacyOptions()).Run(context.Background())

			require.Error(t, err)
			assert.ErrorIs(t, err, panicCause)
			assert.NotContains(t, err.Error(), "do-not-expose")
			assert.Zero(t, tt.stream.saveCalls)
		})
	}
}

func TestLegacyDecodeConvertsFlatFieldsWithoutSilentDefaults(t *testing.T) {
	message := validLegacyMessage("1710000000000-0", 41)
	message.Values["ministryrequestid"] = int64(72)
	message.Values["documentmasterid"] = float64(73)
	message.Values["outputdocumentmasterid"] = "74"
	message.Values["originaldocumentmasterid"] = []byte("75")
	message.Values["documentid"] = uint16(76)
	message.Values["incompatible"] = "1"
	message.Values["needsocr"] = "false"
	message.Values["attributes"] = `{
		"filesize":"100",
		"compressedsize":50,
		"convertedfilesize":25,
		"incompatible":"false",
		"isattachment":true,
		"divisions":[{"divisionid":"9"},{"divisionid":10}],
		"pages":3,
		"label":"retained"
	}`

	delivery, err := decodeLegacyMessage(message, config.WorkloadNormal)

	require.NoError(t, err)
	assert.Equal(t, "1710000000000-0", delivery.StreamID)
	assert.Equal(t, config.WorkloadNormal, delivery.Workload)
	assert.Equal(t, 41, delivery.Message.JobID)
	assert.Equal(t, 72, delivery.Message.MinistryRequestID)
	assert.Equal(t, 73, delivery.Message.DocumentMasterID)
	require.NotNil(t, delivery.Message.OutputDocumentMasterID)
	assert.Equal(t, 74, *delivery.Message.OutputDocumentMasterID)
	require.NotNil(t, delivery.Message.OriginalDocumentMasterID)
	assert.Equal(t, 75, *delivery.Message.OriginalDocumentMasterID)
	require.NotNil(t, delivery.Message.DocumentID)
	assert.Equal(t, 76, *delivery.Message.DocumentID)
	assert.True(t, delivery.Message.Incompatible)
	assert.Equal(t, 100, delivery.Message.Attributes["filesize"])
	assert.Equal(t, 50, delivery.Message.Attributes["compressedsize"])
	assert.Equal(t, 25, delivery.Message.Attributes["convertedfilesize"])
	assert.Equal(t, false, delivery.Message.Attributes["incompatible"])
	assert.Equal(t, true, delivery.Message.Attributes["isattachment"])
	assert.Equal(t, []models.Division{{DivisionID: 9}, {DivisionID: 10}}, delivery.Message.Attributes["divisions"])
	assert.Equal(t, float64(3), delivery.Message.Attributes["pages"])
	assert.Equal(t, "retained", delivery.Message.Attributes["label"])
}

func TestLegacyDecodeRejectsEveryMalformedConversionWithJobCorrelation(t *testing.T) {
	tests := []struct {
		name   string
		mutate func(map[string]any)
	}{
		{
			name: "ministry request identifier",
			mutate: func(values map[string]any) {
				values["ministryrequestid"] = "numeric-secret"
			},
		},
		{
			name: "document master identifier overflow",
			mutate: func(values map[string]any) {
				values["documentmasterid"] = float64(math.MaxInt64)
			},
		},
		{
			name: "optional identifier",
			mutate: func(values map[string]any) {
				values["documentid"] = 4.5
			},
		},
		{
			name: "top level boolean",
			mutate: func(values map[string]any) {
				values["incompatible"] = "boolean-secret"
			},
		},
		{
			name: "ignored legacy boolean",
			mutate: func(values map[string]any) {
				values["needsocr"] = []string{"boolean-secret"}
			},
		},
		{
			name: "attributes JSON",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"token":"attribute-secret"`
			},
		},
		{
			name: "attributes object",
			mutate: func(values map[string]any) {
				values["attributes"] = `["attribute-secret"]`
			},
		},
		{
			name: "attribute numeric",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"filesize":1.5,"token":"attribute-secret"}`
			},
		},
		{
			name: "attribute boolean",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"isattachment":"boolean-secret"}`
			},
		},
		{
			name: "division collection",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"divisions":{"token":"division-secret"}}`
			},
		},
		{
			name: "division item",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"divisions":["division-secret"]}`
			},
		},
		{
			name: "division identifier missing",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"divisions":[{"token":"division-secret"}]}`
			},
		},
		{
			name: "division identifier invalid",
			mutate: func(values map[string]any) {
				values["attributes"] = `{"divisions":[{"divisionid":"division-secret"}]}`
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			message := validLegacyMessage("1710000000000-0", 41)
			tt.mutate(message.Values)

			delivery, err := decodeLegacyMessage(message, config.WorkloadNormal)

			require.Error(t, err)
			assert.Equal(t, 41, delivery.Message.JobID)
			assert.Equal(t, "1710000000000-0", delivery.StreamID)
			assert.Equal(t, config.WorkloadNormal, delivery.Workload)
			assert.Empty(t, delivery.Message.S3FilePath)
			assert.NotContains(t, err.Error(), "secret")
		})
	}
}

func validLegacyOptions() LegacyOptions {
	return LegacyOptions{
		StreamKey:     "legacy:compression",
		CheckpointKey: "legacy:checkpoint",
		StartID:       "0",
		Workload:      config.WorkloadNormal,
	}
}

func validLegacyMessage(id string, jobID int) LegacyMessage {
	return LegacyMessage{
		ID: id,
		Values: map[string]any{
			"jobid":                    jobID,
			"s3filepath":               "s3://citz-test-e/folder/input.pdf",
			"filename":                 "input.pdf",
			"ministryrequestid":        "72",
			"documentmasterid":         "73",
			"outputdocumentmasterid":   "74",
			"originaldocumentmasterid": "75",
			"documentid":               "76",
			"trigger":                  "new",
			"createdby":                "user@example.com",
			"requestnumber":            "CITZ-123",
			"batch":                    "batch-1",
			"incompatible":             "false",
			"usertoken":                "sensitive-token",
			"bcgovcode":                "CITZ",
			"attributes":               `{"pages":3}`,
			"compresseds3filepath":     "",
		},
	}
}

func singleMessageLegacyStream(message LegacyMessage) *fakeLegacyStream {
	stream := &fakeLegacyStream{lastID: "0"}
	stream.readFunc = func(context.Context, string, string) ([]LegacyMessage, error) {
		return []LegacyMessage{message}, nil
	}
	return stream
}

type terminalizingLegacyRepository struct {
	failCalls   int
	failedJobID int
	failureCode store.FailureCode
}

func (r *terminalizingLegacyRepository) WithinJobLock(
	ctx context.Context,
	_ int,
	callback func(context.Context) error,
) (bool, error) {
	return true, callback(ctx)
}

func (*terminalizingLegacyRepository) Latest(
	context.Context,
	int,
) (store.Job, bool, error) {
	return store.Job{}, false, nil
}

func (*terminalizingLegacyRepository) EnsureStarted(
	_ context.Context,
	message models.CompressionProducerMessage,
	workload config.Workload,
) (store.Job, error) {
	return store.Job{
		JobID:         message.JobID,
		Version:       2,
		Status:        store.StatusStarted,
		Workload:      workload,
		WorkloadKnown: true,
		CreatedAt:     time.Now(),
	}, nil
}

func (*terminalizingLegacyRepository) Complete(
	context.Context,
	models.CompressionProducerMessage,
	store.CompressionResult,
) (store.Job, error) {
	return store.Job{}, errors.New("complete must not be called for malformed delivery")
}

func (r *terminalizingLegacyRepository) Fail(
	_ context.Context,
	jobID int,
	code store.FailureCode,
) (store.Job, error) {
	r.failCalls++
	r.failedJobID = jobID
	r.failureCode = code
	return store.Job{JobID: jobID, Version: 3, Status: store.StatusError}, nil
}

type malformedLegacyCompressor struct{}

func (malformedLegacyCompressor) Compress(
	_ context.Context,
	message models.CompressionProducerMessage,
) (store.CompressionResult, error) {
	if message.JobID <= 0 || strings.TrimSpace(message.S3FilePath) != "" {
		return store.CompressionResult{}, errors.New("expected correlated poison delivery")
	}
	return store.CompressionResult{}, compression.NewDeterministicFailure(
		store.FailureCodeInvalidMessage,
		errors.New("malformed legacy delivery"),
	)
}
