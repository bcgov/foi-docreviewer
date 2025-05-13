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
	err := db.conn.QueryRow(query, ocrJob.Documentid, ocrJob.Ministryrequestid).Scan(&currentVersion)
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
		(version, documentid, ministryrequestid, status, message, createdat, createdby) 
		VALUES ($1, $2, $3, $4, $5, NOW(), 'azureocrjob')
		 RETURNING ocrjobid;
	`

	_, inserterr := db.conn.Exec(insertQuery, newVersion, ocrJob.Documentid, ocrJob.Ministryrequestid, ocrJob.Status, ocrJob.Message)
	if inserterr != nil {
		return -1, fmt.Errorf("error inserting new record: %v", err)
	}
	db.Close()
	return 1, nil
}

func (db *DB) insertS3FilePath(message types.OCRJob) (int64, error) {
	var currentDocumentMasterId *int // Use a pointer to check for NULL
	query := `
		SELECT documentmasterid 
		FROM public."Documents" 
		WHERE documentid = $1 AND ministryrequestid = $2 
		ORDER BY version DESC 
		LIMIT 1;
	`

	// Fetch the current version if it exists
	err := db.conn.QueryRow(query, message.Documentid, message.Ministryrequestid).Scan(&currentDocumentMasterId)
	if err != nil && err != sql.ErrNoRows {
		return -1, fmt.Errorf("error querying current version: %v", err)
	}
	if currentDocumentMasterId != nil {
		insertQuery := `
			UPDATE "DocumentMaster"
			SET ocrfilepath = $2
			WHERE documentmasterid = $1
			AND EXISTS (
				SELECT 1
				FROM "OCRJob" oj
				LEFT JOIN "DocumentDeleted" dd 
					ON dd.ministryrequestid = $3
					AND "DocumentMaster".filepath ILIKE dd.filepath || '%'
				WHERE oj.documentmasterid = "DocumentMaster".documentmasterid
					AND oj.status = 'completed'
					AND (dd.filepath IS NULL OR dd.deleted IS FALSE OR dd.deleted IS NULL)
			);
		`
		res, err := db.conn.Exec(
			insertQuery,
			currentDocumentMasterId,
			message.OCRfilepath,       // $2
			message.Ministryrequestid, // $3
		)
		if err != nil {
			log.Printf("ERROR in Exec: %v\n", err)
			return -1, fmt.Errorf("failed to update ocr file path in DocumentMaster: %w", err)
		} else {
			rowsAffected, _ := res.RowsAffected()
			log.Printf("Rows updated: %d\n", rowsAffected)
		}
		log.Println("Update ocr file path in DocumentMaster")
	}
	// Insert the new record
	// insertQuery := `
	// 	INSERT INTO public."DocumentOCRJob"
	// 	(version, documentid, ministryrequestid, status, message, createdat, createdby)
	// 	VALUES ($1, $2, $3, $4, $5, NOW(), 'azureextractjob')
	// 	 RETURNING ocrjobid;
	// `

	// _, inserterr := db.conn.Exec(insertQuery, newVersion, ocrJob.Documentid, ocrJob.Ministryrequestid, ocrJob.Status, ocrJob.Message)
	// if inserterr != nil {
	// 	return -1, fmt.Errorf("error inserting new record: %v", err)
	// }
	db.Close()
	return 1, nil
}

func UpdateDocreviewerTables(ocrJob types.OCRJob) (int64, error) {
	// Replace with your PostgreSQL connection string
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
	id, err := db.insertocrjobdata(ocrJob)
	if err != nil {
		log.Fatalf("Failed to insert ocr job data: %v", err)
		return -1, err
	}
	if ocrJob.Status == "ocrsucceeded" && ocrJob.OCRfilepath != "" {
		_, err = db.insertS3FilePath(ocrJob)
		if err != nil {
			log.Fatalf("Failed to insert ocr s3 filepath: %v", err)
			return -1, err
		}
	}
	return id, nil
}
