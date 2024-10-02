package main

import (
	"awsdocextractservices/redisservices"
	"fmt"
	"os"
	"os/signal"

	"github.com/gocraft/work"
)

type FOIMessageContext struct {
	ministryrequestID int64
	requestnumber     string
	documenthashcode  string
	documents3uri     string
	filename          string
	attributes        map[string]string
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
	if err := job.ArgError(); err != nil {
		return err
	}
	fmt.Println(fmt.Sprintf("Document extraction for : request number %s, for ministry request Id %d", requestnumber, ministryrequestID))
	// Go ahead and send the email...
	// sendEmailTo(addr, subject)

	return nil
}
