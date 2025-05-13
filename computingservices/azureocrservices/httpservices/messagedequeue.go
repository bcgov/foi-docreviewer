package httpservices

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"azureocrservice/types"
	"azureocrservice/utils"
)

// ActiveMQ REST API configuration
var activeMQBaseURL = utils.ViperEnvVariable("activeMQBaseURL")
var username = utils.ViperEnvVariable("activeMQUserName")
var password = utils.ViperEnvVariable("activeMQPassword")

// ProcessMessage fetches messages from the ActiveMQ queue using HTTP
func ProcessMessage() ([]types.QueueMessage, error) {
	queueName := "foidococr"
	// Construct the URL to fetch messages from the queue
	url := fmt.Sprintf("%s/%s?type=queue", activeMQBaseURL, queueName)
	messages := []types.QueueMessage{}
	timeoutCounter := 0
	maxTimeouts := 1
	for {
		//GET request to fetch the message
		message, err := fetchMessageFromQueue(url)
		if err != nil {
			if errors.Is(err, context.DeadlineExceeded) {
				timeoutCounter++
				fmt.Printf("No messages received within the timeout (%d/%d)\n", timeoutCounter, maxTimeouts)
				if timeoutCounter >= maxTimeouts {
					fmt.Println("No more messages in the queue. Exiting...")
					break
				}
				continue
			}
			return nil, fmt.Errorf("error fetching message: %w", err)
		}
		if message == nil {
			fmt.Println("No more messages in the queue. Exiting...")
			break
		}
		fmt.Printf("Extracted s3uri: %s\n", message.CompressedS3FilePath)
		messages = append(messages, *message)
	}
	fmt.Println("All messages processed. Exiting.")
	return messages, nil
}

// Fetches a message from the queue
func fetchMessageFromQueue(url string) (*types.QueueMessage, error) {
	fmt.Println("URL:", url)
	client := &http.Client{Timeout: 30 * time.Second}
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.SetBasicAuth(username, password)
	// Make the HTTP request
	resp, err := client.Do(req)
	fmt.Println("resp:", resp)
	if err != nil {
		return nil, fmt.Errorf("error making HTTP request: %w", err)
	}
	defer resp.Body.Close()
	fmt.Printf("HTTP Status Code: %d\n", resp.StatusCode)
	// Handle non-200 HTTP responses
	if resp.StatusCode != http.StatusOK {
		if resp.StatusCode == http.StatusNoContent {
			// No messages in the queue
			return nil, nil
		}
		return nil, fmt.Errorf("unexpected response status: %s", resp.Status)
	}
	// Parse the response body
	body, err := io.ReadAll(resp.Body)
	fmt.Println("body:", body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}
	fmt.Printf("Response Body: %s\n", string(body))
	var message types.QueueMessage
	if err := json.Unmarshal(body, &message); err != nil {
		return nil, fmt.Errorf("failed to unmarshal message: %w", err)
	}
	return &message, nil
}
