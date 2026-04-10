package dbservice

import (
	httpservice "OpenInfoServices/lib/http"
	"database/sql"
	"fmt"
	"log"
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
	openstatus_ready        = "ready for sitemap"
	openstatus_unpublish    = "unpublished"
)

type AdditionalFile struct {
	Additionalfileid int
	Filename         string
	S3uripath        string
	Isactive         bool
}

type OpenInfoRecord struct {
	Openinfoid                  int
	Foiministryrequestid        int
	Axisrequestid               string
	Description                 string
	Published_date              string
	Contributor                 string
	Applicant_type              string
	Fees                        float64
	BCgovcode                   string
	Sitemap_pages               string
	Type                        string
	Additionalfiles             []AdditionalFile
	Foirequestid                int
	Proactivedisclosureid       int
	Proactivedisclosurecategory string // proactive disclosure categories
	Reportperiod                string // proactive disclosure report period
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

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', 'publishingservice', $3, $4, sitemap_pages
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version for status: %v", err)
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
			r.foirequestid,
			mr.axisrequestid,
			mr.description,
			to_char(oi.publicationdate, 'YYYY-MM-DD') AS publicationdate,
			pa.name as contributor,
			ac.name as applicant_type,
			COALESCE((fee.feedata->>'amountpaid')::Numeric, 0) as fees,
			LOWER(pa.bcgovcode),
			COALESCE(oi.sitemap_pages, '') as sitemap_pages,
			'publish' as type,
			oifiles.additionalfileid,
			oifiles.filename,
			oifiles.s3uripath,
			oifiles.isactive,
			0 as proactivedisclosureid,
			'' as proactivedisclosurecategory
			'' as reportperiod
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
		INNER JOIN public."OpenInformationStatuses" oistatus on mr.oistatus_id = oistatus.oistatusid
		INNER JOIN public."OpenInfoPublicationStatuses" oirequesttype on oi.oipublicationstatus_id = oirequesttype.oipublicationstatusid
		LEFT JOIN public."FOIOpenInfoAdditionalFiles" oifiles on mr.foiministryrequestid = oifiles.ministryrequestid
		WHERE (oistatus.name = '%s' or oistatus.name = '%s') and oirequesttype.name = '%s' and oi.publicationdate < '%s' and oi.processingstatus is NULL and mr.isactive = TRUE
	`, openstate_ready, openstate_published, oirequesttype_publish, tomorrow.Format(dateformat))

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	oiRecordsMap := make(map[int]*OpenInfoRecord)
	for rows.Next() {
		var openinfoid, proactivedisclosureid, foiministryrequestid, foirequestid, additionalfileid sql.NullInt64
		var axisrequestid, description, published_date, contributor, applicant_type, bcgovcode, sitemap_pages, queuetype, filename, s3uripath, proactivedisclosurecategory, reportperiod sql.NullString
		var fees sql.NullFloat64
		var isactive bool

		err := rows.Scan(
			&openinfoid,
			&foiministryrequestid,
			&foirequestid,
			&axisrequestid,
			&description,
			&published_date,
			&contributor,
			&applicant_type,
			&fees,
			&bcgovcode,
			&sitemap_pages,
			&queuetype,
			&additionalfileid,
			&filename,
			&s3uripath,
			&isactive,
			&proactivedisclosureid,
			&proactivedisclosurecategory,
			&reportperiod,
		)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result for prepublish: %w", err)
		}

		if openinfoid.Valid && foiministryrequestid.Valid && foirequestid.Valid && axisrequestid.Valid && description.Valid && published_date.Valid && contributor.Valid && applicant_type.Valid && fees.Valid && bcgovcode.Valid && sitemap_pages.Valid && queuetype.Valid {
			if _, ok := oiRecordsMap[int(foiministryrequestid.Int64)]; !ok {
				oiRecordsMap[int(foiministryrequestid.Int64)] = &OpenInfoRecord{
					Openinfoid:                  int(openinfoid.Int64),
					Foiministryrequestid:        int(foiministryrequestid.Int64),
					Foirequestid:                int(foirequestid.Int64),
					Axisrequestid:               axisrequestid.String,
					Description:                 description.String,
					Published_date:              published_date.String,
					Contributor:                 contributor.String,
					Applicant_type:              applicant_type.String,
					Fees:                        fees.Float64,
					BCgovcode:                   bcgovcode.String,
					Sitemap_pages:               sitemap_pages.String,
					Type:                        queuetype.String,
					Proactivedisclosureid:       int(proactivedisclosureid.Int64),
					Proactivedisclosurecategory: proactivedisclosurecategory.String,
					Reportperiod:                reportperiod.String,
				}
			}

			if additionalfileid.Valid && filename.Valid && s3uripath.Valid {
				oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles = append(oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles, AdditionalFile{
					Additionalfileid: int(additionalfileid.Int64),
					Filename:         filename.String,
					S3uripath:        s3uripath.String,
					Isactive:         isactive,
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
			r.foirequestid,
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
			&record.Foirequestid,
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
		fmt.Printf("DB service - ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Fees)
	}

	err = rows.Err()
	if err != nil {
		return records, fmt.Errorf("failed to retrieve query result: %w", err)
	}

	return records, nil
}

// this function is no longer used. unpublish will be processed in API call instead of cronjobs
func GetOIRecordsForUnpublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	qry := fmt.Sprintf(`
		SELECT
			oi.foiopeninforequestid,
			mr.axisrequestid,
			mr.foiministryrequestid,
			COALESCE(oi.sitemap_pages, '') as sitemap_pages,
			'unpublish' as type
		FROM public."FOIOpenInformationRequests" oi
		INNER JOIN public."FOIMinistryRequests" mr on oi.foiministryrequest_id = mr.foiministryrequestid and mr.isactive = TRUE
		INNER JOIN public."OpenInformationStatuses" oistatus on mr.oistatus_id = oistatus.oistatusid
		INNER JOIN public."OpenInfoPublicationStatuses" oirequesttype on oi.oipublicationstatus_id = oirequesttype.oipublicationstatusid
		WHERE oirequesttype.name = '%s' and (oi.processingstatus IS NULL or oi.processingstatus != '%s') and oi.isactive = TRUE
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
			&record.Foiministryrequestid,
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

func UpdateOIRecordState(db *sql.DB, foiflowapi string, foiministryrequestid int, foirequestid int, publishingstatus string, message string, sitemap_pages string, oistatusid int) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', NULL, $3, $4, $5
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message, sitemap_pages)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version for sitemaps: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	// Update request state in FOIMinistryRequests
	// endpoint
	section := "oistatusid"
	endpoint := fmt.Sprintf("%s/api/foirequests/%d/ministryrequest/%d/section/%s", foiflowapi, foirequestid, foiministryrequestid, section)
	fmt.Println(endpoint)

	// payload
	payload := map[string]int{"oistatusid": oistatusid}
	_, err = httpservice.HttpPost(endpoint, payload)

	return err
}

func GetFoirequestID(db *sql.DB, foiministryrequestid int) (int, error) {

	// Query to get foirequestid
	var foirequestid int
	query := `
		SELECT foirequest_id
		FROM public."FOIMinistryRequests"
		WHERE foiministryrequestid=$1
		ORDER BY version DESC
		LIMIT 1
	`

	// Execute the query
	err := db.QueryRow(query, foiministryrequestid).Scan(&foirequestid)
	if err != nil {
		return 0, fmt.Errorf("failed to retrieve foirequestid: %w", err)
	}

	return foirequestid, err
}

func LogError(db *sql.DB, foiministryrequestid int, publishingstatus string, message string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', NULL, $3, $4, sitemap_pages
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting error message: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}

// ================ Proactive Disclosure ================

func UpdatePDOIRecordStatus(db *sql.DB, foiministryrequestid int, publishingstatus string, message string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIProactiveDisclosureRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND (isactive = true OR isactive IS NULL)`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Adjust oipublicationstatus_id for FOIPDRequest based on publishingstatus
	var oipublicationstatusid int;
	if publishingstatus == "unpublished" {
		oipublicationstatusid = 3
	} else {
		oipublicationstatusid = 2
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIProactiveDisclosureRequests" (foiministryrequest_id, foiministryrequestversion_id, proactivedisclosurecategoryid, reportperiod, publicationdate, created_at, createdby, updated_at, updatedby, version, oipublicationstatus_id, earliesteligiblepublicationdate, processingstatus, processingmessage, sitemap_pages, isactive)
        SELECT foiministryrequest_id, foiministryrequestversion_id, proactivedisclosurecategoryid, reportperiod, publicationdate, $2, 'publishingservice', NULL, NULL, version + 1, $5, earliesteligiblepublicationdate, $3, $4, sitemap_pages, true
        FROM public."FOIProactiveDisclosureRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message, oipublicationstatusid)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version for status: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}

func GetPDOIRecordsForPrePublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	// var record PDOpenInfoRecord

	// Get the current time
	now := time.Now()
	// Add 24 hours to the current time
	tomorrow := now.Add(24 * time.Hour)

	qry := fmt.Sprintf(`
		SELECT
			pd.proactivedisclosureid,
			mr.foiministryrequestid,
			r.foirequestid,
			mr.axisrequestid,
			mr.description,
			to_char(pd.publicationdate, 'YYYY-MM-DD') AS publicationdate,
			pa.name as contributor,
			ac.name as applicant_type,
			COALESCE((fee.feedata->>'amountpaid')::Numeric, 0) as fees,
			LOWER(pa.bcgovcode),
			COALESCE(pd.sitemap_pages, '') as sitemap_pages,
			'publish' as type,
			pdc.name as proactivedisclosurecategory,
			pd.reportperiod,
			oifiles.additionalfileid,
			oifiles.filename,
			oifiles.s3uripath,
			oifiles.isactive,
			0 as openinfoid
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
		INNER JOIN public."FOIProactiveDisclosureRequests" pd on mr.foiministryrequestid = pd.foiministryrequest_id and pd.isactive = TRUE
		INNER JOIN public."ProactiveDisclosureCategories" pdc on pd.proactivedisclosurecategoryid = pdc.proactivedisclosurecategoryid
		INNER JOIN public."OpenInformationStatuses" oistatus on mr.oistatus_id = oistatus.oistatusid
		INNER JOIN public."OpenInfoPublicationStatuses" oirequesttype on pd.oipublicationstatus_id = oirequesttype.oipublicationstatusid
		LEFT JOIN public."FOIOpenInfoAdditionalFiles" oifiles on mr.foiministryrequestid = oifiles.ministryrequestid
		WHERE (oistatus.name = '%s' or oistatus.name = '%s') and oirequesttype.name = '%s' and pd.publicationdate < '%s' and pd.processingstatus is NULL and mr.isactive = TRUE
	`, openstate_ready, openstate_published, oirequesttype_publish, tomorrow.Format(dateformat))

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	oiRecordsMap := make(map[int]*OpenInfoRecord)
	for rows.Next() {
		var openinfoid, proactivedisclosureid, foiministryrequestid, foirequestid, additionalfileid sql.NullInt64
		var axisrequestid, description, published_date, contributor, applicant_type, bcgovcode, sitemap_pages, queuetype, filename, s3uripath, proactivedisclosurecategory, reportperiod sql.NullString
		var fees sql.NullFloat64
		var isactive bool

		err := rows.Scan(
			&proactivedisclosureid,
			&foiministryrequestid,
			&foirequestid,
			&axisrequestid,
			&description,
			&published_date,
			&contributor,
			&applicant_type,
			&fees,
			&bcgovcode,
			&sitemap_pages,
			&queuetype,
			&proactivedisclosurecategory,
			&reportperiod,
			&additionalfileid,
			&filename,
			&s3uripath,
			&isactive,
			&openinfoid,
		)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result for prepublish: %w", err)
		}

		if proactivedisclosureid.Valid && foiministryrequestid.Valid && foirequestid.Valid && axisrequestid.Valid && description.Valid && published_date.Valid && contributor.Valid && applicant_type.Valid && fees.Valid && bcgovcode.Valid && sitemap_pages.Valid && queuetype.Valid {
			if _, ok := oiRecordsMap[int(foiministryrequestid.Int64)]; !ok {
				oiRecordsMap[int(foiministryrequestid.Int64)] = &OpenInfoRecord{
					Proactivedisclosureid:       int(proactivedisclosureid.Int64),
					Foiministryrequestid:        int(foiministryrequestid.Int64),
					Foirequestid:                int(foirequestid.Int64),
					Axisrequestid:               axisrequestid.String,
					Description:                 description.String,
					Published_date:              published_date.String,
					Contributor:                 contributor.String,
					Applicant_type:              applicant_type.String,
					Fees:                        fees.Float64,
					BCgovcode:                   bcgovcode.String,
					Sitemap_pages:               sitemap_pages.String,
					Type:                        queuetype.String,
					Proactivedisclosurecategory: proactivedisclosurecategory.String,
					Reportperiod:                reportperiod.String,
					Openinfoid:                  int(openinfoid.Int64),
				}
			}

			if additionalfileid.Valid && filename.Valid && s3uripath.Valid {
				oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles = append(oiRecordsMap[int(foiministryrequestid.Int64)].Additionalfiles, AdditionalFile{
					Additionalfileid: int(additionalfileid.Int64),
					Filename:         filename.String,
					S3uripath:        s3uripath.String,
					Isactive:         isactive,
				})
			}
		}

		// records = append(records, record)
		// fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Category: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Proactivedisclosurecategory)
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

func GetPDOIRecordsForPublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	qry := fmt.Sprintf(`
		SELECT
			pd.proactivedisclosureid,
			mr.foiministryrequestid,
			r.foirequestid,
			mr.axisrequestid,
			mr.description,
			pd.publicationdate,
			pa.name as contributor,
			ac.name as applicant_type,
			COALESCE((fee.feedata->>'amountpaid')::Numeric, 0) as fees,
			LOWER(pa.bcgovcode) as bcgovcode,
			pdc.name as proactivedisclosurecategory
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
		INNER JOIN public."FOIProactiveDisclosureRequests" pd on mr.foiministryrequestid = pd.foiministryrequest_id and pd.isactive = TRUE
		INNER JOIN public."ProactiveDisclosureCategories" pdc on pd.proactivedisclosurecategoryid = pdc.proactivedisclosurecategoryid
		WHERE pd.processingstatus = '%s' and mr.isactive = TRUE
	`, openstatus_ready)

	rows, err := db.Query(qry)
	if err != nil {
		return records, fmt.Errorf("query failed: %w", err)
	}
	defer rows.Close()

	for rows.Next() {
		err := rows.Scan(
			&record.Proactivedisclosureid,
			&record.Foiministryrequestid,
			&record.Foirequestid,
			&record.Axisrequestid,
			&record.Description,
			&record.Published_date,
			&record.Contributor,
			&record.Applicant_type,
			&record.Fees,
			&record.BCgovcode,
			&record.Proactivedisclosurecategory)
		if err != nil {
			return records, fmt.Errorf("failed to retrieve query result: %w", err)
		}
		records = append(records, record)
		fmt.Printf("DB service - ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Category: %v\n", record.Axisrequestid, record.Description, record.Published_date, record.Contributor, record.Applicant_type, record.Proactivedisclosurecategory)
	}

	err = rows.Err()
	if err != nil {
		return records, fmt.Errorf("failed to retrieve query result: %w", err)
	}

	return records, nil
}

func UpdatePDOIRecordState(db *sql.DB, foiflowapi string, foiministryrequestid int, foirequestid int, publishingstatus string, message string, sitemap_pages string, oistatusid int) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIProactiveDisclosureRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND (isactive = true OR isactive IS NULL)`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIProactiveDisclosureRequests" (foiministryrequest_id, foiministryrequestversion_id, proactivedisclosurecategoryid, reportperiod, publicationdate, created_at, createdby, updated_at, updatedby, version, oipublicationstatus_id, earliesteligiblepublicationdate, processingstatus, processingmessage, sitemap_pages, isactive)
        SELECT foiministryrequest_id, foiministryrequestversion_id, proactivedisclosurecategoryid, reportperiod, publicationdate, $2, 'publishingservice', NULL, NULL, version + 1, oipublicationstatus_id, earliesteligiblepublicationdate, $3, $4, $5, true
        FROM public."FOIProactiveDisclosureRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message, sitemap_pages)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting new version for sitemaps: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	// Update request state in FOIMinistryRequests
	// endpoint
	section := "oistatusid"
	endpoint := fmt.Sprintf("%s/api/foirequests/%d/ministryrequest/%d/section/%s", foiflowapi, foirequestid, foiministryrequestid, section)
	fmt.Println(endpoint)

	// payload
	payload := map[string]int{"oistatusid": oistatusid}
	_, err = httpservice.HttpPost(endpoint, payload)

	return err
}

func LogPDError(db *sql.DB, foiministryrequestid int, publishingstatus string, message string) error {

	// Begin a transaction
	tx, err := db.Begin()
	if err != nil {
		log.Fatalf("Error beginning transaction: %v", err)
	}

	// Set previous versions' isactive to false
	_, err = tx.Exec(`UPDATE public."FOIOpenInformationRequests" SET isactive = false, updated_at = $2, updatedby = 'publishingservice' WHERE foiministryrequest_id = $1 AND isactive = true`, foiministryrequestid, time.Now())
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error updating previous versions: %v", err)
	}

	// Insert a new version of the record
	_, err = tx.Exec(`
        INSERT INTO public."FOIOpenInformationRequests" (version, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, isactive, copyrightsevered, created_at, updated_at, createdby, updatedby, processingstatus, processingmessage, sitemap_pages)
        SELECT version + 1, foiministryrequest_id, foiministryrequestversion_id, oipublicationstatus_id, oiexemption_id, oiassignedto, oiexemptionapproved, pagereference, iaorationale, oifeedback, publicationdate, true, copyrightsevered, $2, NULL, 'publishingservice', NULL, $3, $4, sitemap_pages
        FROM public."FOIOpenInformationRequests"
        WHERE foiministryrequest_id = $1 AND isactive = false
        ORDER BY version DESC
        LIMIT 1
    `, foiministryrequestid, time.Now(), publishingstatus, message)
	if err != nil {
		tx.Rollback()
		log.Fatalf("Error inserting error message: %v", err)
	}

	// Commit the transaction
	err = tx.Commit()
	if err != nil {
		log.Fatalf("Error committing transaction: %v", err)
	}

	return err
}
