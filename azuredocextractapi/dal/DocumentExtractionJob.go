package dal

import (
	"azuredocextractapi/types"
	"azuredocextractapi/utils"
	"database/sql"
	"fmt"
	"log"
)

// InsertUser inserts a new user into the database
func (db *DB) insertextractiondata(extractionJob types.ExtractionJob) (int64, error) {
	var currentVersion *int // Use a pointer to check for NULL
	query := `
		SELECT version 
		FROM public."DocumentExtractionJob" 
		WHERE documentid = $1 AND ministryrequestid = $2 
		ORDER BY version DESC 
		LIMIT 1;
	`

	// Fetch the current version if it exists
	err := db.conn.QueryRow(query, extractionJob.Documentid, extractionJob.Ministryrequestid).Scan(&currentVersion)
	if err != nil && err != sql.ErrNoRows {
		return -1, fmt.Errorf("error querying current version: %v", err)
	}

	// Determine the new version
	var newVersion int
	if currentVersion != nil {
		newVersion = *currentVersion + 1
	} else {
		newVersion = 1
	}

	// Insert the new record
	insertQuery := `
		INSERT INTO public."DocumentExtractionJob" 
		(version, documentid, ministryrequestid, status, message, createdat, createdby) 
		VALUES ($1, $2, $3, $4, $5, NOW(), 'azureextractjob')
		 RETURNING extractionjobid;
	`

	_, inserterr := db.conn.Exec(insertQuery, newVersion, extractionJob.Documentid, extractionJob.Ministryrequestid, extractionJob.Status, extractionJob.Message)
	if inserterr != nil {
		return -1, fmt.Errorf("error inserting new record: %v", err)
	}
	db.Close()
	return 1, nil
}

func UpdateExtractionJob(extractionJob types.ExtractionJob) (int64, error) {
	// Replace with your PostgreSQL connection string
	dataSource := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		utils.ViperEnvVariable("AZDOCEXTRACT_FOIDOCREVIEWER_DB_HOST"), utils.ViperEnvVariable("AZDOCEXTRACT_FOIDOCREVIEWER_DB_PORT"),
		utils.ViperEnvVariable("AZDOCEXTRACT_FOIDOCREVIEWER_DB_USERNAME"), utils.ViperEnvVariable("AZDOCEXTRACT_FOIDOCREVIEWER_DB_PASSWORD"),
		utils.ViperEnvVariable("AZDOCEXTRACT_FOIDOCREVIEWER_DB_NAME"),
	)

	// Initialize the database connection
	db, err := NewDB(dataSource)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	id, err := db.insertextractiondata(extractionJob)
	if err != nil {
		log.Fatalf("Failed to insert user: %v", err)
		return -1, err
	}

	return id, nil
}
