package dbservice

import (
	"database/sql"
	"fmt"
	"log"
	"strconv"
	"time"

	_ "github.com/lib/pq"
)

const (
	dateformat              = "2006-01-02"
	openstate_ready         = "Ready to Publish"
	openstate_published     = "Published"
	openstate_unpublish     = "Unpublish"
	oirequesttype_publish   = "Publish"
	oirequesttype_unpublish = "Unpublish Request"
	openstatus_ready        = "ready"
	openstatus_unpublish    = "unpublished"
)

type AdditionalFile struct {
	Additionalfileid int
	Filename         string
	S3uripath        string
}

type OpenInfoRecord struct {
	Openinfoid           int
	Foiministryrequestid int
	Axisrequestid        string
	Description          string
	Published_date       string
	Contributor          string
	Applicant_type       string
	Fees                 float64
	BCgovcode            string
	Sitemap_pages        string
	Type                 string
	Additionalfiles      []AdditionalFile
}

func Conn(dsn string) (*sql.DB, error) {
	db, err := sql.Open("postgres", dsn)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to database: %w", err)
	}

	err = db.Ping()
	if err != nil {
		db.Close()
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// fmt.Println("Successfully connected!")
	return db, nil
}

func UpdateOIRecordStatus(db *sql.DB, foiministryrequestid int, publishingstatus string, message string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Step 1: Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Step 2: Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages, oistatusid)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', 'publishingservice', '$3', '$4', sitemap_pages, oistatusid
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}

func GetOIRecordsForPrePublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	// var record OpenInfoRecord

	// Get the current time
	now := time.Now()
	// Add 24 hours to the current time
	tomorrow := now.Add(24 * time.Hour)

	qry := fmt.Sprintf(`
		SELECT
			oi.foiopeninforequestid,
			mr.foiministryrequestid,
			mr.axisrequestid,
			mr.description,
			oi.publicationdate,
			pa.name as contributor,
			ac.name as applicant_type,
			COALESCE((fee.feedata->>'amountpaid')::Numeric, 0) as fees,
			LOWER(pa.bcgovcode),
			COALESCE(oi.sitemap_pages, '') as sitemap_pages,
			'publish' as type
		FROM public."FOIMinistryRequests" mr
		INNER JOIN public."FOIRequests" r on mr.foirequest_id = r.foirequestid and mr.foirequestversion_id = r.version
		INNER JOIN public."ProgramAreas" pa on mr.programareaid = pa.programareaid
		INNER JOIN public."ApplicantCategories" ac on r.applicantcategoryid = ac.applicantcategoryid
		LEFT JOIN (
			SELECT ministryrequestid, MAX(version) as max_version
			FROM public."FOIRequestCFRFees"
			GROUP BY ministryrequestid
		) latest_payment on mr.foiministryrequestid = latest_payment.ministryrequestid
		LEFT JOIN public."FOIRequestCFRFees" fee on mr.foiministryrequestid = fee.ministryrequestid 
			and latest_payment.max_version = fee.version and mr.version = fee.ministryrequestversion
		INNER JOIN public."FOIOpenInformationRequests" oi on mr.foiministryrequestid = oi.foiministryrequest_id and oi.isactive = TRUE
		INNER JOIN public."OpenInformationStatuses" oistatus on oi.oistatusid = oistatus.oistatusid
		INNER JOIN public."OpenInfoPublicationStatuses" oirequesttype on oi.oipublicationstatus_id = oirequesttype.oipublicationstatusid
		LEFT JOIN public."FOIOpenInfoAdditionalFiles" oifiles on 
		WHERE (oistatus.name = '%s' or oistatus.name = '%s') and oirequesttype.name = '%s' and oi.publicationdate < '%s' and oi.processingstatus is NULL and mr.isactive = TRUE
	`, openstate_ready, openstate_published, oirequesttype_publish, tomorrow.Format(dateformat))

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	oiRecordsMap := make(map[int]*OpenInfoRecord)
	for rows.Next() {
		var openinfoid, foiministryrequestid, additionalfileid sql.NullInt64
		var axisrequestid, description, published_date, contributor, applicant_type, bcgovcode, sitemap_pages, queuetype, filename, s3uripath sql.NullString
		var fees sql.NullFloat64

		// err := rows.Scan(
		// 	&record.Openinfoid,
		// 	&record.Foiministryrequestid,
		// 	&record.Axisrequestid,
		// 	&record.Description,
		// 	&record.Published_date,
		// 	&record.Contributor,
		// 	&record.Applicant_type,
		// 	&record.Fees,
		// 	&record.BCgovcode,
		// 	&record.Sitemap_pages,
		// 	&record.Type,
		// )
		err := rows.Scan(
			&openinfoid,
			&foiministryrequestid,
			&axisrequestid,
			&description,
			&published_date,
			&contributor,
			&applicant_type,
			&fees,
			&bcgovcode,
			&sitemap_pages,
			&queuetype,
		)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result for prepublish: %w", err)
		}

		if openinfoid.Valid && foiministryrequestid.Valid && axisrequestid.Valid && description.Valid && published_date.Valid && contributor.Valid && applicant_type.Valid && fees.Valid && bcgovcode.Valid && sitemap_pages.Valid && queuetype.Valid {
			if _, ok := oiRecordsMap[int(foiministryrequestid.Int64)]; !ok {
				oiRecordsMap[int(foiministryrequestid.Int64)] = &OpenInfoRecord{
					Openinfoid:           int(openinfoid.Int64),
					Foiministryrequestid: int(foiministryrequestid.Int64),
					Axisrequestid:        axisrequestid.String,
					Description:          description.String,
					Published_date:       published_date.String,
					Contributor:          contributor.String,
					Applicant_type:       applicant_type.String,
					Fees:                 fees.Float64,
					BCgovcode:            bcgovcode.String,
					Sitemap_pages:        sitemap_pages.String,
					Type:                 queuetype.String,
				}
			}

			if additionalfileid.Valid && filename.Valid && s3uripath.Valid {
				oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles = append(oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles, AdditionalFile{
					Additionalfileid: int(foiministryrequestid.Int64),
					Filename:         filename.String,
					S3uripath:        s3uripath.String,
				})
			}
		}

		// records = append(records, record)
		// fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Fees)
	}

	err = rows.Err()
	if err != nil {
		return records, fmt.Errorf("failed to retrieve query result: %w", err)
	}

	for _, record := range oiRecordsMap {
		records = append(records, *record)
	}

	return records, nil
}

func GetOIRecordsForPublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	qry := fmt.Sprintf(`
		SELECT
			oi.foiopeninforequestid,
			mr.foiministryrequestid,
			mr.axisrequestid,
			mr.description,
			oi.publicationdate,
			pa.name as contributor,
			ac.name as applicant_type,
			COALESCE((fee.feedata->>'amountpaid')::Numeric, 0) as fees,
			LOWER(pa.bcgovcode) as bcgovcode
		FROM public."FOIMinistryRequests" mr
		INNER JOIN public."FOIRequests" r on mr.foirequest_id = r.foirequestid and mr.foirequestversion_id = r.version
		INNER JOIN public."ProgramAreas" pa on mr.programareaid = pa.programareaid
		INNER JOIN public."ApplicantCategories" ac on r.applicantcategoryid = ac.applicantcategoryid
		LEFT JOIN (
			SELECT ministryrequestid, MAX(version) as max_version
			FROM public."FOIRequestCFRFees"
			GROUP BY ministryrequestid
		) latest_payment on mr.foiministryrequestid = latest_payment.ministryrequestid
		LEFT JOIN public."FOIRequestCFRFees" fee on mr.foiministryrequestid = fee.ministryrequestid 
			and latest_payment.max_version = fee.version and mr.version = fee.ministryrequestversion
		INNER JOIN public."FOIOpenInformationRequests" oi on mr.foiministryrequestid = oi.foiministryrequest_id and oi.isactive = TRUE
		WHERE oi.processingstatus = '%s' and mr.isactive = TRUE
	`, openstatus_ready)

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		err := rows.Scan(
			&record.Openinfoid,
			&record.Foiministryrequestid,
			&record.Axisrequestid,
			&record.Description,
			&record.Published_date,
			&record.Contributor,
			&record.Applicant_type,
			&record.Fees,
			&record.BCgovcode)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result: %w", err)
		}
		records = append(records, record)
		fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Fees)
	}

	err = rows.Err()
	if err != nil {
		return records, fmt.Errorf("failed to retrieve query result: %w", err)
	}

	return records, nil
}

func GetOIRecordsForUnpublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	qry := fmt.Sprintf(`
		SELECT
			oi.foiopeninforequestid,
			mr.axisrequestid,
			COALESCE(oi.sitemap_pages, '') as sitemap_pages,
			'unpublish' as type
		FROM public."FOIOpenInformationRequests" oi
		INNER JOIN public."FOIMinistryRequests" mr on oi.foiministryrequest_id = mr.foiministryrequestid and mr.isactive = TRUE
		INNER JOIN public."OpenInformationStatuses" oistatus on oi.oistatusid = oistatus.oistatusid
		INNER JOIN public."OpenInfoPublicationStatuses" oirequesttype on oi.oipublicationstatus_id = oirequesttype.oipublicationstatusid
		WHERE oirequesttype.name = '%s' and oi.processingstatus != '%s' and oi.isactive = TRUE
	`, oirequesttype_unpublish, openstatus_unpublish)

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		err := rows.Scan(
			&record.Openinfoid,
			&record.Axisrequestid,
			&record.Sitemap_pages,
			&record.Type,
		)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result: %w", err)
		}
		records = append(records, record)
		fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Fees)
	}

	err = rows.Err()
	if err != nil {
		return records, fmt.Errorf("failed to retrieve query result: %w", err)
	}

	return records, nil
}

func UpdateOIRecordState(db *sql.DB, foiministryrequestid int, publishingstatus string, message string, state string, sitemap_pages string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Retrieve oipublicationstatus_id based on oistatus
	var oistatusid int
	err = tx.QueryRow(`SELECT oistatusid FROM public."OpenInformationStatuses" WHERE name = $1`, state).Scan(&oistatusid)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error retrieving oistatusid: %v", err)
	}

	// Step 1: Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Step 2: Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages, oistatusid)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', NULL, '$3', '$4', '$5', $6
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message, sitemap_pages, strconv.Itoa(oistatusid))
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}

func LogError(db *sql.DB, foiministryrequestid int, publishingstatus string, message string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Step 1: Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Step 2: Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages, oistatusid)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', NULL, '$3', '$4', sitemap_pages, oistatusid
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}
