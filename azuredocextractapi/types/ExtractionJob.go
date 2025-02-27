package types

type ExtractionJob struct {
	Extractionjobid   int    `json:"extractionjobid"`
	Version           int    `json:"version"`
	Documentid        int    `json:"documentid"`
	Ministryrequestid int    `json:"ministryrequestid"`
	Status            string `json:"status"`
	Message           string `json:"message"`
}
