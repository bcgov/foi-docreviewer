package types

type OCRJob struct {
	OCRjobid          int    `json:"ocrjobid"`
	Version           int    `json:"version"`
	Documentid        int    `json:"documentid"`
	Ministryrequestid int    `json:"ministryrequestid"`
	Status            string `json:"status"`
	OCRfilepath       string `json:"ocrfilepath,omitempty"`
	//Documentmasterid  string `json:"documentmasterid"`
	Message string `json:"message"`
}
