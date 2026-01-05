package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	//cfg := utils.LoadConfig()
	// create temp folder for pdfcpu
	configDir := "/tmp/pdfcpu_config"
	os.MkdirAll(configDir, 0o777)
	// set XDG_CONFIG_HOME, which pdfcpu uses
	os.Setenv("XDG_CONFIG_HOME", configDir)
	consumerID := flag.String("consumer-id", "$", "ID of the consumer")
	startFrom := flag.String("start-from", "$", "Where to start from in stream: 0 or $")
	// Parse CLI flags
	flag.Parse()
	fmt.Printf("Starting consumer with ID: %s, Start from: %s\n", *consumerID, *startFrom)
	Start(*consumerID, StartFrom(*startFrom))
}
