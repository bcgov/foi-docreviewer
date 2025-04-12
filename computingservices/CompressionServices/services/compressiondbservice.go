package services

import (
	"fmt"
	"log"

	"compressionservices/models"
	"compressionservices/utils"
)

func RecordJobStart(msg *models.CompressionProducerMessage) {
	db := utils.GetDBConnection()
	defer db.Close()

	exists := doesJobVersionExist(msg.JobID, 2)
	if !exists {
		stmt, err := db.Prepare(`
            INSERT INTO public."CompressionJob"
            (compressionjobid, version, ministryrequestid, batch, trigger, filename, status,inputdocumentmasterid)
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

func RecordJobEnd(msg *models.CompressionProducerMessage, isError bool, message string) {
	// Get DB connection
	db := utils.GetDBConnection()
	defer db.Close()
	// Check if job version exists
	exists := doesJobVersionExist(msg.JobID, 3)
	if !exists {
		status := "completed"
		if !isError {
			// Query to insert into DocumentMaster and CompressionJob tables using CTE
			query := `
				WITH masterid AS (
					INSERT INTO "DocumentMaster"
					(filepath, ministryrequestid, processingparentid, isredactionready, createdby)
					VALUES ($1, $2, $3, $4, $5)
					RETURNING documentmasterid
				)
				INSERT INTO "CompressionJob"
				(compressionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, outputdocumentmasterid, filename, status, message)
				VALUES ($6, $7, $8, $9, $10, $11, (SELECT documentmasterid FROM masterid), $12, $13, $14)
				RETURNING (SELECT documentmasterid FROM masterid)
			`
			stmt, err := db.Prepare(query)
			if err != nil {
				log.Printf("Error preparing statement: %v", err)
				return
			}
			defer stmt.Close()
			var returnedDocMasterID int
			// Execute the query and retrieve the document master ID
			err = stmt.QueryRow(
				msg.S3FilePath,        // $1
				msg.MinistryRequestID, // $2
				msg.DocumentMasterID,  // $3
				false,                 // $4
				"compressionservice",  // $5
				msg.JobID,             // $6
				3,                     // $7 (version number)
				msg.MinistryRequestID, // $8
				msg.Batch,             // $9
				msg.Trigger,           // $10
				msg.DocumentMasterID,  // $11
				msg.Filename,          // $12
				status,                // $13
				message,               // $14 (jobMessage)
			).Scan(&returnedDocMasterID)

			if err != nil {
				log.Printf("Error executing query: %v", err)
				return
			}
			fmt.Println("Returned DocumentMasterID:", returnedDocMasterID)
		} else {
			// Handle the error case
			status := "error"
			_, err := db.Exec(`
				INSERT INTO public."CompressionJob"
                (compressionjobid, version, ministryrequestid, batch, trigger, filename, status,inputdocumentmasterid)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
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
			)
			if err != nil {
				log.Printf("Error inserting CompressionJob end: %v", err)
				panic(err)
			}
		}
	} else {
		fmt.Printf("Compression Job already exists for file %s with JOB ID %d and version %d\n", msg.Filename, msg.JobID, 3)
	}
}

func doesJobVersionExist(jobID int, version int) bool {
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
	db := utils.GetDBConnection()
	defer db.Close()

	var dedupeInProgress, dedupeError, dedupeCompleted int
	err := db.QueryRow(`
		SELECT
			COUNT(1) FILTER (WHERE status = 'pushedtostream' OR status = 'started') AS inprogress,
			COUNT(1) FILTER (WHERE status = 'error') AS error,
			COUNT(1) FILTER (WHERE status = 'completed') AS completed
		FROM (
			SELECT MAX(version) AS version, deduplicationjobid
			FROM public."DeduplicationJob"
			WHERE batch = $1
			GROUP BY deduplicationjobid
		) sq
		JOIN public."DeduplicationJob" dj
		ON dj.deduplicationjobid = sq.deduplicationjobid AND dj.version = sq.version`,
		batch).Scan(&dedupeInProgress, &dedupeError, &dedupeCompleted)
	if err != nil {
		fmt.Printf("Error querying compression job state: %v\n", err)
		panic(err)
	}
	if dedupeInProgress > 0 {
		return false, dedupeError > 0
	}

	var compInProgress, compError, compCompleted int
	err = db.QueryRow(`
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

	return compInProgress == 0 && dedupeInProgress == 0, (dedupeError + compError) > 0
}

// from . import getdbconnection
// from models import compressionproducermessage
// from utils.basicutils import to_json
// from datetime import datetime
// import json

// def savedocumentdetails(compressionproducermessage, hashcode, pagecount = 1):
//     conn = getdbconnection()
//     try:
//         cursor = conn.cursor()

//         _incompatible = True if str(compressionproducermessage.incompatible).lower() == 'true' else False

//         cursor.execute('INSERT INTO public."Documents" (version, \
//         filename, documentmasterid,foiministryrequestid,createdby,created_at,statusid,incompatible, originalpagecount, pagecount) VALUES(%s::integer, %s, %s,%s::integer,%s,%s,%s::integer,%s::bool,%s::integer,%s::integer) RETURNING documentid;',
//         (1, compressionproducermessage.filename, compressionproducermessage.outputdocumentmasterid or compressionproducermessage.documentmasterid,
//         compressionproducermessage.ministryrequestid,'{"user":"dedupeservice"}',datetime.now(),1,_incompatible,pagecount,pagecount))
//         conn.commit()
//         id_of_new_row = cursor.fetchone()

//         if (compressionproducermessage.attributes.get('isattachment', False) and compressionproducermessage.trigger == 'recordreplace'):
//             documentmasterid = compressionproducermessage.originaldocumentmasterid or compressionproducermessage.documentmasterid
//         else:
//             documentmasterid = compressionproducermessage.documentmasterid

//         cursor.execute('''UPDATE public."DocumentAttributes" SET attributes = %s WHERE documentmasterid = %s''',
//           (json.dumps(compressionproducermessage.attributes), documentmasterid))
//         conn.commit()

//         cursor.execute('INSERT INTO public."DocumentHashCodes" (documentid, \
//         rank1hash,created_at) VALUES(%s::integer, %s,%s)', (id_of_new_row, hashcode,datetime.now()))
//         conn.commit()

//         cursor.close()
//         return True
//     except(Exception) as error:
//         print("Exception while executing func savedocumentdetails (p5), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()

// def recordjobstart(compressionproducermessage):
//     conn = getdbconnection()
//     try:
//         if __doesjobversionexists(compressionproducermessage.jobid, 2) == False:
//             cursor = conn.cursor()
//             cursor.execute('''INSERT INTO public."CompressionJob"
//                 (compressionjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
//                 VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s) on conflict (compressionjobid, version) do nothing returning compressionjobid;''',
//                 (compressionproducermessage.jobid, 2, compressionproducermessage.ministryrequestid, compressionproducermessage.batch, 'rank1', compressionproducermessage.trigger, compressionproducermessage.documentmasterid, compressionproducermessage.filename, 'started'))
//             conn.commit()
//             cursor.close()
//         else:
//             print("Dedupe Job  already exists for file {0} with JOB ID {1} and version {2}".format(compressionproducermessage.filename,compressionproducermessage.jobid,2))
//     except(Exception) as error:
//         print("Exception while executing func recordjobstart (p6), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()

// def recordjobend(compressionproducermessage, error, message=""):
//     conn = getdbconnection()
//     try:
//         if __doesjobversionexists(compressionproducermessage.jobid, 3) == False:
//             cursor = conn.cursor()
//             cursor.execute('''INSERT INTO public."CompressionJob"
//                 (compressionjobid, version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status, message)
//                 VALUES (%s::integer, %s::integer, %s::integer, %s, %s, %s, %s, %s, %s, %s) on conflict (compressionjobid, version) do nothing returning compressionjobid;''',
//                 (compressionproducermessage.jobid, 3, compressionproducermessage.ministryrequestid, compressionproducermessage.batch, 'rank1', compressionproducermessage.trigger, compressionproducermessage.documentmasterid, compressionproducermessage.filename,
//                 'error' if error else 'completed', message if error else ""))
//             conn.commit()
//             cursor.close()
//         else:
//             print("Dedupe Job  already exists for file {0} with JOB ID {1} and version {2}".format(compressionproducermessage.filename,compressionproducermessage.jobid,3))
//     except(Exception) as error:
//         print("Exception while executing func recordjobend (p7), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()

// def __doesjobversionexists(jobid, version):
//     conn = getdbconnection()
//     result = 0
//     try:
//         cursor = conn.cursor()
//         cursor.execute('''SELECT count(compressionjobid) FROM public."CompressionJob"  where compressionjobid = %s::integer and version = %s::integer''',(jobid, version))
//         count = cursor.fetchone()[0]
//         result = count
//         cursor.close()

//     except(Exception) as error:
//         print("Exception while executing func __doesversionexists (p9), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()
//     return False if result == 0 else True

// def updateredactionstatus(compressionproducermessage):
//     conn = getdbconnection()
//     try:
//         cursor = conn.cursor()
//         cursor.execute('''update "DocumentMaster" dm
//                         set isredactionready = true, updatedby  = 'dedupeservice', updated_at = now()
//                         from(
//                         select distinct on (documentmasterid) documentmasterid, version, status
//                         from  "DeduplicationJob"
//                         where ministryrequestid= %s::integer
//                         order by documentmasterid, version desc) as sq
//                         where dm.documentmasterid = sq.documentmasterid
//                         and isredactionready = false and sq.status = 'completed' and ministryrequestid = %s::integer''',
//             (compressionproducermessage.ministryrequestid,compressionproducermessage.ministryrequestid))
//         conn.commit()
//         cursor.close()
//     except(Exception) as error:
//         print("Exception while executing func updateredactionstatus (p8), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()

// def isbatchcompleted(batch):
//     conn = getdbconnection()
//     try:
//         cursor = conn.cursor()
//         cursor.execute('''select count(1) filter (where status = 'pushedtostream' or status = 'started') as inprogress,
//             count(1) filter (where status = 'error') as error,
//             count(1) filter (where status = 'completed') as completed
//             from (select max(version) as version,  deduplicationjobid
//             from public."DeduplicationJob"
//             where batch = %s
//             group by deduplicationjobid) sq
//             join public."DeduplicationJob" dj
//                 on dj.deduplicationjobid = sq.deduplicationjobid
//                 and dj.version = sq.version;''',
//             (batch,)
//         )
//         (dedupeinprogress, dedupeerr, _dedupecompleted) = cursor.fetchone()
//         if dedupeinprogress > 0:
//             cursor.close()
//             conn.close()
//             return False, dedupeerr > 0
//         cursor.execute('''select count(1) filter (where status = 'pushedtostream' or status = 'started') as inprogress,
//             count(1) filter (where status = 'error') as error,
//             count(1) filter (where status = 'completed') as completed
//             from (select max(version) as version,  compressionjobid
//             from public."CompressionJob"
//             where batch = %s
//             group by compressionjobid) sq
//             join public."CompressionJob" dj
//                 on dj.compressionjobid = sq.compressionjobid
//                 and dj.version = sq.version;''',
//             (batch,)
//         )
//         (compressioninprogress, compressionerr, _compressioncompleted) = cursor.fetchone()
//         cursor.close()
//         return compressioninprogress == 0 and dedupeinprogress == 0, compressionerr+dedupeerr > 0
//     except(Exception) as error:
//         print("Exception while executing func isbatchcompleted (p2), Error : {0} ".format(error))
//         raise
//     finally:
//         if conn is not None:
//             conn.close()

// def pagecalculatorjobstart(message):
//         conn = getdbconnection()
//         try:

//             cursor = conn.cursor()
//             cursor.execute('''INSERT INTO public."PageCalculatorJob"
//                 (version, ministryrequestid, inputmessage, status, createdby)
//                 VALUES (%s::integer, %s::integer, %s, %s, %s) returning pagecalculatorjobid;''',
//                 (1, message.ministryrequestid, to_json(message), 'pushedtostream', 'dedupeservice'))
//             pagecalculatorjobid = cursor.fetchone()[0]
//             conn.commit()
//             cursor.close()
//             print("Inserted pagecalculatorjobid:", pagecalculatorjobid)
//             return pagecalculatorjobid
//         except(Exception) as error:
//             print("Exception while executing func recordjobstart (p6), Error : {0} ".format(error))
//             raise
//         finally:
//             if conn is not None:
//                 conn.close()
