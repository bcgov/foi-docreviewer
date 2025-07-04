package services

import (
	"fmt"
	"log"

	"ocrservices/models"
	"ocrservices/utils"
)

func RecordJobStart(msg *models.OCRProducerMessage) {
	db := utils.GetDBConnection()
	defer db.Close()
	print("msg.JobID", msg.JobID)
	exists := doesOCRActiveMQJobVersionExist(msg.JobID, 2)
	if !exists {
		stmt, err := db.Prepare(`
            INSERT INTO public."OCRActiveMQJob"
            (ocractivemqjobid, version, ministryrequestid, batch, trigger, filename, status, documentmasterid)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (ocractivemqjobid, version) DO NOTHING;
        `)
		if err != nil {
			fmt.Printf("Error inserting OCR Job start: %v\n", err)
			panic(err)
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
			fmt.Printf("Error inserting OCR Job start: %v\n", err)
		}
		return
	} else {
		fmt.Printf("OCR Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, 2)
	}
}

func RecordJobEnd(msg *models.OCRProducerMessage, isError bool, message string) error {

	db := utils.GetDBConnection()
	defer db.Close()
	exists := doesOCRActiveMQJobVersionExist(msg.JobID, 3)
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
					VALUES ($1, $2, $3, $4, $5, $6, $7, $8) ON CONFLICT (ocractivemqjobid, version) DO NOTHING;
				`
		stmt, err := db.Prepare(query)
		if err != nil {
			log.Printf("Error preparing statement: %v", err)
			return err
		}
		defer stmt.Close()
		_, err = stmt.Exec(
			msg.JobID,
			3,
			msg.MinistryRequestID,
			msg.Batch,
			msg.Trigger,
			msg.DocumentMasterID,
			msg.Filename,
			status, // $8
		)
		if err != nil {
			log.Printf("Error executing query: %v", err)
			return err
		}
		return nil
	} else {
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
			log.Printf("Error inserting OCR Job end: %v", err)
			return err
			// panic(err)
		}
		return nil
	}
}

func doesOCRActiveMQJobVersionExist(jobID int, version int) bool {
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
			SELECT MAX(version) AS version, ocractivemqjobid
			FROM public."OCRActiveMQJob"
			WHERE batch = $1
			GROUP BY ocractivemqjobid
		) sq
		JOIN public."OCRActiveMQJob" dj
		ON dj.ocractivemqjobid = sq.ocractivemqjobid AND dj.version = sq.version`,
		batch).Scan(&compInProgress, &compError, &compCompleted)
	if err != nil {
		fmt.Printf("Error querying compression job state: %v\n", err)
		panic(err)
	}
	// fmt.Printf("compInProgress: %v\n", compInProgress)
	// fmt.Printf("compError: %v\n", compError)
	return compInProgress == 0, compError > 0
	//return compInProgress == 0 &&dedupeInProgress == 0, (dedupeError + compError) > 0
}
