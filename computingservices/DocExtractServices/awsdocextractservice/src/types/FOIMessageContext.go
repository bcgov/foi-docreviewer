package foimessagetypes

type FOIMessageContext struct {
	ministryrequestID int64
	requestnumber     string
	documenthashcode  string
	documents3uri     string
	filename          string
	attributes        map[string]string
}
