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
	log.Println("newVersion:", newVersion)
	// Insert the new record
	insertQuery := `
		INSERT INTO public."DocumentOCRJob" 
		(version, documentid, ministryrequestid, documentmasterid, status, message, createdat, createdby) 
		VALUES ($1, $2, $3, $4, $5, $6, NOW(), 'azureocrjob');
	`
	_, inserterr := db.conn.Exec(insertQuery, newVersion, ocrJob.DocumentId, ocrJob.MinistryRequestID, ocrJob.DocumentMasterID, ocrJob.Status, ocrJob.Message)
	if inserterr != nil {
		return -1, fmt.Errorf("error inserting new record: %v", inserterr)
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
	// insertQuery := `
	// 		UPDATE "DocumentMaster"
	// 		SET ocrfilepath = $2,
	// 		isredactionready = true,
	// 		updated_at=NOW(),
	// 		updatedby='azureocrservice'
	// 		WHERE documentmasterid = $1
	// 		AND ministryrequestid=$3
	// 	`
	insertQuery := `
		UPDATE "DocumentMaster"
		SET ocrfilepath = $2,
			isredactionready = true,
			updated_at = NOW(),
			updatedby = 'azureocrservice'
		WHERE documentmasterid = (
			SELECT 
				CASE 
					WHEN processingparentid IS NOT NULL THEN processingparentid 
					ELSE documentmasterid 
				END
			FROM "DocumentMaster"
			WHERE documentmasterid = $1
		)
		AND ministryrequestid = $3
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

func (db *DB) updateFileSizeinDocAttributes(message types.OCRJob) (int64, error) {
	fmt.Printf("MasterId: %v\n", message.DocumentMasterID)
	fmt.Printf("filezisee: %v\n", message.OCRFileSize)
	query := `
		UPDATE "DocumentAttributes"
		SET attributes = (attributes::jsonb || jsonb_build_object('ocrfilesize', $2::integer))::json
		WHERE documentmasterid = (
			SELECT 
				CASE 
					WHEN processingparentid IS NOT NULL THEN processingparentid 
					ELSE documentmasterid 
				END
			FROM "DocumentMaster"
			WHERE documentmasterid = $1::integer
		)
		AND isactive = true;
	`
	result, inserterr := db.conn.Exec(query, message.DocumentMasterID, message.OCRFileSize)
	if inserterr != nil {
		return -1, fmt.Errorf("failed to update documentmasterid: %w", inserterr)
	}
	rowsAffected, _ := result.RowsAffected()
	fmt.Printf("Rows updated in DocumentAttributes: %d\n", rowsAffected)
	return 1, inserterr
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
	var ocrJobErr error
	if ocrJob.Status != "ocrfileuploadsuccess" && ocrJob.OCRFilePath == "" {
		id, ocrJobErr = db.insertocrjobdata(ocrJob)
		if ocrJobErr != nil {
			log.Printf("Failed to insert ocr job data: %v", ocrJobErr)
			return -1, ocrJobErr
		}
	} else if ocrJob.Status == "ocrfileuploadsuccess" && ocrJob.OCRFilePath != "" {
		_, filepathUpdateErr := db.insertOCRS3FilePath(ocrJob)
		if filepathUpdateErr != nil {
			log.Printf("Failed to insert ocr s3 filepath: %v", filepathUpdateErr)
			return -1, filepathUpdateErr
		}
		_, attributesDbErr := db.updateFileSizeinDocAttributes(ocrJob)
		if attributesDbErr != nil {
			log.Printf("Failed to insert ocr s3 filepath: %v", attributesDbErr)
			return -1, attributesDbErr
		}
	}
	return id, nil
}
