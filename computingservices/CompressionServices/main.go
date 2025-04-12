package main

import (
	"compressionservices/utils"
	"flag"
	"fmt"
	"log"
	"os"
)

func main() {
	dir, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("Current working directory:", dir)
	cfg := utils.LoadConfig()
	// Define CLI flags similar to Typer arguments
	consumerID := flag.String("consumer-id", "consumer1", "ID of the consumer")
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
