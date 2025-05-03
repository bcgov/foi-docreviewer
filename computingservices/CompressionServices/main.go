package main

import (
	"compressionservices/utils"
	"flag"
	"fmt"
)

func main() {
	cfg := utils.LoadConfig()
	consumerID := flag.String("consumer-id", "$", "ID of the consumer")
	startFrom := flag.String("start-from", "$", "Where to start from in stream: 0 or $")
	// Parse CLI flags
	flag.Parse()
	fmt.Printf("Starting consumer with ID: %s, Start from: %s\n", *consumerID, *startFrom)
	// Call your actual stream processor
	Start(*consumerID, StartFrom(*startFrom), cfg)
}

// from services import foirediscompressionconsumer

//  if __name__ == '__main__':
//     foirediscompressionconsumer.app()
