package main

import (
	"fmt"
	"os"
	"os/signal"

	"github.com/gocraft/work"

	"awsdocextractservices/redisservices"
	"awsdocextractservices/s3services"
)

type FOIMessageContext struct {
	ministryrequestID int64
	requestnumber     string
	documenthashcode  string
	documents3uri     string
	filename          string
	attributes        map[string]string
	s3bucket          string
}

func main() {

	redisPool := redisservices.GetFOIRedisConnectionPool()

	pool := work.NewWorkerPool(FOIMessageContext{}, 10, "foi_documentextract_namespace", redisPool)

	pool.Job("document_extract", DocumentExtract)

	// Start processing jobs
	pool.Start()

	// Wait for a signal to quit:
	signalChan := make(chan os.Signal, 1)
	signal.Notify(signalChan, os.Interrupt, os.Kill)
	<-signalChan

	// Stop the pool
	pool.Stop()

}

func DocumentExtract(job *work.Job) error {
	// Extract arguments:
	ministryrequestID := job.ArgInt64("ministryrequestID")
	requestnumber := job.ArgString("requestnumber")
	documents3uri := job.ArgString("documents3uri")
	if err := job.ArgError(); err != nil {
		return err
	}
	fmt.Println(fmt.Sprintf("Document extraction for : request number %s, for ministry request Id %d", requestnumber, ministryrequestID))
	// Go ahead and send the email...
	// sendEmailTo(addr, subject)

	if documents3uri != "" {
		s3services.GetFilefroms3(documents3uri)
	}

	return nil
}
