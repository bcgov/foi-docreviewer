package services

import (
	"fmt"
	"log"

	"compressionservices/models"
	"compressionservices/utils"
)

func RecordCompressionJobStart(msg *models.CompressionProducerMessage) {
	db := utils.GetDBConnection()
	defer db.Close()

	exists := doesCompressionJobVersionExist(msg.JobID, 2)
	if !exists {
		stmt, err := db.Prepare(`
            INSERT INTO public."CompressionJob"
            (compressionjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (compressionjobid, version) DO NOTHING;
        `)
		if err != nil {
			fmt.Printf("Error inserting CompressionJob start: %v\n", err)
			panic(err)
			//return
		}
		defer stmt.Close()
		_, err = stmt.Exec(
			msg.JobID,
			2,
			msg.MinistryRequestID,
			msg.Batch,
			msg.Trigger,
			msg.Filename,
			"started",
			msg.DocumentMasterID,
		)
		if err != nil {
			//return fmt.Errorf("failed to execute insert: %w", err)
			fmt.Printf("Error inserting CompressionJob start: %v\n", err)
		}
		return
		// _, err := db.Exec(`
		// 	INSERT INTO public."CompressionJob"
		// 	(compressionjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
		// 	VALUES ($1::integer, $2::integer, $3::integer, $4, $5, $6, $7, $8, $9)
		// 	ON CONFLICT (compressionjobid, version) DO NOTHING;`,
		// 	msg.JobID, 2, msg.MinistryRequestID, msg.Batch, "rank1", msg.Trigger,
		// 	msg.DocumentMasterID, msg.Filename, "started",
		// )
		// if err != nil {
		// 	fmt.Printf("Error inserting CompressionJob start: %v\n", err)
		// 	panic(err)
		// }
	} else {
		fmt.Printf("Compression Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, 2)
	}
}

//ADD LOGIC::if msg.Attributes.IsAttachment{}

func RecordCompressionJobEnd(s3FilePath string, msg *models.CompressionProducerMessage, isError bool, message string) error {
	if s3FilePath == "" {
		s3FilePath = msg.S3FilePath
	}
	db := utils.GetDBConnection()
	defer db.Close()
	exists := doesCompressionJobVersionExist(msg.JobID, 3)
	if exists {
		fmt.Printf("Compression Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, 3)
		return nil
	}
	// Determine job status
	status := "completed"
	if isError {
		status = "error"
	}
	if !isError {
		query := `
					INSERT INTO "CompressionJob"
					(compressionjobid, version, ministryrequestid, batch, trigger, documentmasterid, filename, status)
					VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
				`
		stmt, err := db.Prepare(query)
		if err != nil {
			log.Printf("Error preparing statement: %v", err)
			return err
		}
		defer stmt.Close()
		_, err = stmt.Exec(
			msg.JobID,             // $1
			3,                     // $2
			msg.MinistryRequestID, // $3
			msg.Batch,             // $4
			msg.Trigger,           // $5
			msg.DocumentMasterID,  // $6
			msg.Filename,          // $7
			status,                // $8
		)
		if err != nil {
			log.Printf("Error executing query: %v", err)
			return err
		}
		return nil
	} else {
		fmt.Printf("Compression failed for file: %v\n", s3FilePath)
		_, err := db.Exec(`
			INSERT INTO public."CompressionJob"
			(compressionjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, message)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
			ON CONFLICT (compressionjobid, version) DO NOTHING;
		`,
			msg.JobID,
			3,
			msg.MinistryRequestID,
			msg.Batch,
			msg.Trigger,
			msg.Filename,
			status,
			msg.DocumentMasterID,
			message,
		)
		if err != nil {
			log.Printf("Error inserting CompressionJob end: %v", err)
			return err
			// panic(err)
		}
		return nil
	}
}

func doesCompressionJobVersionExist(jobID int, version int) bool {
	db := utils.GetDBConnection()
	defer db.Close()

	var count int
	err := db.QueryRow(`
		SELECT COUNT(compressionjobid)
		FROM public."CompressionJob"
		WHERE compressionjobid = $1::integer AND version = $2::integer`,
		jobID, version).Scan(&count)
	if err != nil {
		fmt.Printf("Error checking job version exists: %v\n", err)
		panic(err)
	}
	return count > 0
}

func IsBatchCompleted(batch string) (bool, bool) {
	fmt.Printf("\nbatch: %v\n", batch)
	db := utils.GetDBConnection()
	defer db.Close()
	var compInProgress, compError, compCompleted int
	err := db.QueryRow(`
		SELECT
			COUNT(1) FILTER (WHERE status = 'pushedtostream' OR status = 'started') AS inprogress,
			COUNT(1) FILTER (WHERE status = 'error') AS error,
			COUNT(1) FILTER (WHERE status = 'completed') AS completed
		FROM (
			SELECT MAX(version) AS version, compressionjobid
			FROM public."CompressionJob"
			WHERE batch = $1
			GROUP BY compressionjobid
		) sq
		JOIN public."CompressionJob" dj
		ON dj.compressionjobid = sq.compressionjobid AND dj.version = sq.version`,
		batch).Scan(&compInProgress, &compError, &compCompleted)
	if err != nil {
		fmt.Printf("Error querying compression job state: %v\n", err)
		panic(err)
	}
	fmt.Printf("compInProgress: %v\n", compInProgress)
	fmt.Printf("compError: %v\n", compError)
	return compInProgress == 0, compError > 0
	//return compInProgress == 0 &&dedupeInProgress == 0, (dedupeError + compError) > 0
}

func UpdateDocumentDetails(message *models.CompressionProducerMessage, compressedFileSize int, s3CompressedFilePath string) error {

	// if message.Attributes.IsAttachment {

	// }
	// fmt.Println("\nOriginalDocumentMasterID:", message.OriginalDocumentMasterID)
	// fmt.Println("\nOutputDocumentMasterID:", message.OutputDocumentMasterID)
	// fmt.Println("\nDocumentMasterID:", message.DocumentMasterID)
	// docMasterIdToBeUpdated := message.DocumentMasterID
	// if message.OutputDocumentMasterID != nil {
	// 	docMasterIdToBeUpdated = *message.OutputDocumentMasterID
	// }
	db := utils.GetDBConnection()
	defer db.Close()
	query := `
		UPDATE "DocumentAttributes"
		SET attributes = (attributes::jsonb || jsonb_build_object('compressedfilesize', $2::integer))::json
		WHERE documentmasterid = $1::integer
		AND isactive = true;
	`
	var recordID *int
	_, err := db.Exec(query, message.DocumentMasterID, compressedFileSize)
	if err != nil {
		return fmt.Errorf("failed to update documentmasterid: %w", err)
	}
	fmt.Println("DocumentAttributes-attributes updated for documentid:", recordID)
	/**TO DO::Attachment logic needs to be added**/
	fmt.Printf("Type: %T, Value: %#v\n", compressedFileSize, compressedFileSize)
	query = `
		UPDATE "DocumentMaster"
		SET compressedfilepath = $2
		WHERE documentmasterid = $1
		AND EXISTS (
			SELECT 1
			FROM "CompressionJob" cj
			LEFT JOIN "DocumentDeleted" dd 
				ON dd.ministryrequestid = $3
				AND "DocumentMaster".filepath ILIKE dd.filepath || '%'
			WHERE cj.documentmasterid = "DocumentMaster".documentmasterid
				AND cj.status = 'completed'
				AND (dd.filepath IS NULL OR dd.deleted IS FALSE OR dd.deleted IS NULL)
		);
	`
	res, err := db.Exec(
		query,
		message.DocumentMasterID,
		s3CompressedFilePath,      // $2
		message.MinistryRequestID, // $3
	)
	if err != nil {
		log.Printf("ERROR in Exec: %v\n", err)
		return fmt.Errorf("failed to update compressed file path in DocumentMaster: %w", err)
	} else {
		rowsAffected, _ := res.RowsAffected()
		log.Printf("Rows updated: %d\n", rowsAffected)
	}
	log.Println("Update compressed file path in DocumentMaster")
	return nil
}

func UpdateRedactionStatus(msg *models.CompressionProducerMessage) error {
	db := utils.GetDBConnection()
	defer db.Close()
	query := `
        UPDATE "DocumentMaster" dm
        SET isredactionready = true,
            updatedby = 'compressionservice',
            updated_at = now()
        FROM (
            SELECT DISTINCT ON (documentmasterid) documentmasterid, version, status
            FROM "CompressionJob"
            WHERE ministryrequestid = $1
            ORDER BY documentmasterid, version DESC
        ) AS sq
        WHERE dm.documentmasterid = sq.documentmasterid
          AND dm.isredactionready = false
          AND sq.status = 'completed'
          AND dm.ministryrequestid = $1;
    `
	_, err := db.Exec(query, msg.MinistryRequestID)
	if err != nil {
		return fmt.Errorf("error executing updateRedactionStatus query: %w", err)
	}
	fmt.Println("UpdateRedactionStatus - updated")
	return nil
}

func doesOCRJobVersionExist(jobID int, version int) bool {
	db := utils.GetDBConnection()
	defer db.Close()

	var count int
	err := db.QueryRow(`
		SELECT COUNT(ocractivemqjobid)
		FROM public."OCRActiveMQJob"
		WHERE ocractivemqjobid = $1::integer AND version = $2::integer`,
		jobID, version).Scan(&count)
	if err != nil {
		fmt.Printf("Error checking OCR job version exists: %v\n", err)
		panic(err)
	}
	return count > 0
}

func RecordOCRJobStart(msg *models.CompressionProducerMessage) (int, error) {
	db := utils.GetDBConnection()
	defer db.Close()
	const version = 1
	exists := doesOCRJobVersionExist(msg.JobID, version)
	if !exists {
		stmt, err := db.Prepare(`
            INSERT INTO public."OCRActiveMQJob"
            (ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (ocractivemqjobid, version) DO NOTHING;
        `)
		if err != nil {
			fmt.Printf("Error preparing insert statement: %v\n", err)
			return 0, err
		}
		defer stmt.Close()
		_, err = stmt.Exec(
			msg.JobID,
			version,
			msg.MinistryRequestID,
			msg.Batch,
			msg.Trigger,
			msg.Filename,
			"started",
			msg.DocumentMasterID,
		)
		if err != nil {
			fmt.Printf("Error executing insert: %v\n", err)
			return 0, err
		}
		fmt.Printf("OCR Job started and inserted for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, version)
	} else {
		fmt.Printf("OCR Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, version)
	}
	return msg.JobID, nil
}

func RecordOCRJobEnd(s3FilePath string, msg *models.CompressionProducerMessage, isError bool, message string) error {
	if s3FilePath == "" {
		s3FilePath = msg.S3FilePath
	}
	db := utils.GetDBConnection()
	defer db.Close()
	exists := doesOCRJobVersionExist(msg.JobID, 3)
	if exists {
		fmt.Printf("OCR Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, 3)
		return nil
	}
	// Determine job status
	status := "completed"
	if isError {
		status = "error"
	}
	if !isError {
		query := `
					INSERT INTO "OCRActiveMQJob"
					(ocractivemqjobid, version, ministryrequestid, batch, trigger, documentmasterid, filename, status)
					VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
				`
		stmt, err := db.Prepare(query)
		if err != nil {
			log.Printf("Error preparing statement: %v", err)
			return err
		}
		defer stmt.Close()
		_, err = stmt.Exec(
			msg.JobID,             // $1
			3,                     // $2
			msg.MinistryRequestID, // $3
			msg.Batch,             // $4
			msg.Trigger,           // $5
			msg.DocumentMasterID,  // $6
			msg.Filename,          // $7
			status,                // $8
		)
		if err != nil {
			log.Printf("Error executing query: %v", err)
			return err
		}
		return nil
	} else {
		fmt.Printf("OCR failed for file: %v\n", s3FilePath)
		_, err := db.Exec(`
			INSERT INTO public."OCRActiveMQJob"
			(ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid, message)
			VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
			ON CONFLICT (ocractivemqjobid, version) DO NOTHING;
		`,
			msg.JobID,
			3,
			msg.MinistryRequestID,
			msg.Batch,
			msg.Trigger,
			msg.Filename,
			status,
			msg.DocumentMasterID,
			message,
		)
		if err != nil {
			log.Printf("Error inserting OCRActiveMQJob end: %v", err)
			return err
			// panic(err)
		}
		return nil
	}
}

// func UpdateRecordIdInDocMaster(recordID *int, newDocumentMasterId int) error {
// 	db := utils.GetDBConnection()
// 	defer db.Close()
// 	query := `
// 		UPDATE public."DocumentMaster"
// 		SET recordid = $1
// 		WHERE documentmasterid = $2
// 	`
// 	_, err := db.Exec(query, recordID, newDocumentMasterId)
// 	if err != nil {
// 		return fmt.Errorf("failed to update documentmasterid: %w", err)
// 	}
// 	/**TO DO::Attachment logic needs to be added**/
// 	log.Println("Recordid updated in new DocumentMaster entry for ", newDocumentMasterId)
// 	return nil
// }

// func UpdateRedactionStatus(message *models.CompressionProducerMessage) error {
// 	db := utils.GetDBConnection()
// 	defer db.Close()
// 	/**TO DO::Attachment logic needs to be added**/

// 	//Marshal attributes to JSON
// 	// attributesJSON, err := json.Marshal(msg.Attributes)
// 	// if err != nil {
// 	// 	return fmt.Errorf("failed to marshal attributes: %w", err)
// 	// }
// 	/**TO DO:: Add compressedfilesize value in attributes-SET //attributes = $1 and**/
// 	query := `
// 		UPDATE "DocumentMaster" dm
// 			SET isactive = false,
// 				updatedby = 'compressionservice',
// 				updated_at = NOW()
// 			WHERE dm.documentmasterid = sq.inputdocumentmasterid
// 			AND dm.ministryrequestid = $1::integer;
// 	`
// 	rows, err := db.Query(query, message.MinistryRequestID)
// 	if err != nil {
// 		return fmt.Errorf("failed to update DocumentMaster: %w", err)
// 	}
// 	defer rows.Close()
// 	for rows.Next() {
// 		var documentMasterID int
// 		// You can add more fields if you need to print more data
// 		err := rows.Scan(&documentMasterID /*, other fields */)
// 		if err != nil {
// 			log.Fatalf("Row scan failed: %v", err)
// 		}
// 		fmt.Printf("Updated DocumentMasterID: %d\n", documentMasterID)
// 	}
// 	log.Println("RedactionReady status updated successfully.")
// 	return nil
// }
