package dal

import (
	"azuredococrapi/types"
	"azuredococrapi/utils"
	"database/sql"
	"fmt"
	"log"
)

// InsertUser inserts a new user into the database
func (db *DB) insertocrjobdata(ocrJob types.OCRJob) (int64, error) {
	var currentVersion *int // Use a pointer to check for NULL
	query := `
		SELECT version 
		FROM public."DocumentOCRJob" 
		WHERE documentid = $1 AND ministryrequestid = $2 
		ORDER BY version DESC 
		LIMIT 1;
	`
	// Fetch the current version if it exists
	err := db.conn.QueryRow(query, ocrJob.DocumentId, ocrJob.MinistryRequestID).Scan(&currentVersion)
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
		INSERT INTO public."DocumentOCRJob" 
		(version, documentid, ministryrequestid, documentmasterid, status, message, createdat, createdby) 
		VALUES ($1, $2, $3, $4, $5, NOW(), 'azureocrjob');
	`
	_, inserterr := db.conn.Exec(insertQuery, newVersion, ocrJob.DocumentId, ocrJob.MinistryRequestID, ocrJob.DocumentMasterID, ocrJob.Status, ocrJob.Message)
	if inserterr != nil {
		return -1, fmt.Errorf("error inserting new record: %v", err)
	}
	db.Close()
	return 1, nil
}

func (db *DB) insertOCRS3FilePath(message types.OCRJob) (int64, error) {
	var currentDocumentMasterId int // Use a pointer to check for NULL
	query := `
		SELECT documentmasterid 
		FROM public."Documents" 
		WHERE documentid = $1 AND foiministryrequestid = $2 
		ORDER BY version DESC 
		LIMIT 1;
	`

	// Fetch the current version if it exists
	row := db.conn.QueryRow(query, message.DocumentId, message.MinistryRequestID)
	err := row.Scan(&currentDocumentMasterId)
	if err != nil && err != sql.ErrNoRows {
		return -1, fmt.Errorf("error querying current document master: %v", err)
	}
	log.Println("currentDocumentMasterId:", currentDocumentMasterId)
	//if currentDocumentMasterId != nil {
	insertQuery := `
			UPDATE "DocumentMaster"
			SET ocrfilepath = $2,
			isredactionready = true,
			updated_at=NOW(),
			updatedby='azureocrservice'
			WHERE documentmasterid = $1 
			AND ministryrequestid=$3
		`
	res, err := db.conn.Exec(
		insertQuery,
		currentDocumentMasterId,
		message.OCRFilePath,       // $2
		message.MinistryRequestID, // $3
	)
	if err != nil {
		log.Printf("ERROR in Exec: %v\n", err)
		return -1, fmt.Errorf("failed to update ocr file path in DocumentMaster: %w", err)
	} else {
		rowsAffected, _ := res.RowsAffected()
		log.Printf("Rows updated: %d\n", rowsAffected)
	}
	log.Println("Updated ocr file path in DocumentMaster")
	db.Close()
	return 1, nil
}

func UpdateDocreviewerTables(ocrJob types.OCRJob) (int64, error) {
	// Replace with PostgreSQL connection string
	dataSource := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		utils.ViperEnvVariable("AZDOCOCR_FOIDOCREVIEWER_DB_HOST"), utils.ViperEnvVariable("AZDOCOCR_FOIDOCREVIEWER_DB_PORT"),
		utils.ViperEnvVariable("AZDOCOCR_FOIDOCREVIEWER_DB_USERNAME"), utils.ViperEnvVariable("AZDOCOCR_FOIDOCREVIEWER_DB_PASSWORD"),
		utils.ViperEnvVariable("AZDOCOCR_FOIDOCREVIEWER_DB_NAME"),
	)
	// Initialize the database connection
	db, err := NewDB(dataSource)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	var id int64
	if ocrJob.Status != "ocrfileuploadsuccess" && ocrJob.OCRFilePath == "" {
		id, err = db.insertocrjobdata(ocrJob)
		if err != nil {
			log.Fatalf("Failed to insert ocr job data: %v", err)
			return -1, err
		}
	} else if ocrJob.Status == "ocrfileuploadsuccess" && ocrJob.OCRFilePath != "" {
		id, err = db.insertOCRS3FilePath(ocrJob)
		if err != nil {
			log.Fatalf("Failed to insert ocr s3 filepath: %v", err)
			return -1, err
		}
	}
	return id, nil
}
