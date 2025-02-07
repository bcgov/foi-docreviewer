package main

import (
	"azuredocextractapi/dal"
	"azuredocextractapi/types"
	"azuredocextractapi/utils"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"

	"github.com/gorilla/mux"
)

// POST handler for adding a new ExtractionJob
func updateExtractionJob(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	var newJob types.ExtractionJob

	// Decode the JSON body into the ExtractionJob struct
	err := json.NewDecoder(r.Body).Decode(&newJob)
	if err != nil {
		http.Error(w, "Invalid request payload", http.StatusBadRequest)
		return
	}
	extractjobid, _backenderr := dal.UpdateExtractionJob(newJob)
	if _backenderr != nil {
		http.Error(w, "Invalid request payload", http.StatusBadRequest)
		return
	}
	// Respond with the created job
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(extractjobid)
}

func main() {
	router := mux.NewRouter()

	router.HandleFunc("/api/documentextractjob", updateExtractionJob).Methods("POST")
	router.Use(corsMiddleware)
	// Apply middleware to check for custom header
	router.Use(customHeaderMiddleware)

	apilistenPort, err := strconv.Atoi(utils.ViperEnvVariable("AZDOCEXTRACT_LISTENING_PORT"))
	if err != nil {
		fmt.Println("Error converting string to int:", err)
		return
	}

	log.Printf("Server is listening on :%d", apilistenPort)
	log.Fatal(http.ListenAndServe(fmt.Sprintf(":%d", apilistenPort), router))
}

// corsMiddleware adds CORS headers to the response
func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Set CORS headers
		allowedorigins := utils.ViperEnvVariable("AZDOCEXTRACT_ALLOWED_ORIGINS")
		w.Header().Set("Access-Control-Allow-Origin", allowedorigins) // Allow all origins or specify a domain
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

		// Handle preflight request
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusOK)
			return
		}

		// Proceed to the next handler
		next.ServeHTTP(w, r)
	})
}

// Middleware to check for a custom header
func customHeaderMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Check for the custom header
		headerValue := r.Header.Get("X-FOI-Extraction-Secret")
		if headerValue == "" || headerValue != utils.ViperEnvVariable("AZDOCEXTRACT_API_SECRET") {
			http.Error(w, "Missing or invalid custom header", http.StatusForbidden)
			return
		}

		// Continue to the next handler
		next.ServeHTTP(w, r)
	})
}
