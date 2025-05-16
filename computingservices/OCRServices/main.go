package main

import (
	"flag"
	"fmt"
)

func main() {
	consumerID := flag.String("consumer-id", "$", "ID of the consumer")
	startFrom := flag.String("start-from", "$", "Where to start from in stream: 0 or $")
	// Parse CLI flags
	flag.Parse()
	fmt.Printf("Starting consumer with ID: %s, Start from: %s\n", *consumerID, *startFrom)
	Start(*consumerID, StartFrom(*startFrom))
}
