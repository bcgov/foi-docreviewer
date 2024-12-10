package dbservice

import (
	"database/sql"
	"fmt"
	"time"

	_ "github.com/lib/pq"
)

const (
	dateformat           = "2006-01-02"
	openstate_ready      = "Ready for Publishing"
	openstate_unpublish  = "Unpublish"
	openstatus_ready     = "ready"
	openstatus_unpublish = "unpublished"
)

type OpenInfoRecord struct {
	Openinfoid           int
	Foiministryrequestid int
	Axisrequestid        string
	Description          string
	Published_date       string
	Contributor          string
	Applicant_type       string
	Fees                 float32
	BCgovcode            string
	Sitemap_pages        string
	Type                 string
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

func UpdateOIRecordStatus(db *sql.DB, openinfoid int, publishingstatus string, message string) error {

	qry := `
		UPDATE public."OpenInfoPublishing"
		SET
			publishingstatus = $1,
			message = $2
		WHERE openinfoid = $3;
	`
	_, err := db.Exec(qry, publishingstatus, message, openinfoid)
	return err
}

func GetOIRecordsForPrePublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	// Get the current time
	now := time.Now()
	// Add 24 hours to the current time
	tomorrow := now.Add(24 * time.Hour)

	qry := fmt.Sprintf(`
		SELECT
			oi.openinfoid,
			oi.foiministryrequestid,
			mr.axisrequestid,
			mr.description,
			oi.published_date,
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
		INNER JOIN public."OpenInfoPublishing" oi on mr.foiministryrequestid = oi.foiministryrequestid
		WHERE oi.openinfostate = '%s' and oi.published_date < '%s' and oi.publishingstatus is NULL and mr.isactive = TRUE
	`, openstate_ready, tomorrow.Format(dateformat))

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
			&record.BCgovcode,
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

func GetOIRecordsForPublishing(db *sql.DB) ([]OpenInfoRecord, error) {
	var records []OpenInfoRecord
	var record OpenInfoRecord

	qry := fmt.Sprintf(`
		SELECT
			oi.openinfoid,
			oi.foiministryrequestid,
			mr.axisrequestid,
			mr.description,
			oi.published_date,
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
		INNER JOIN public."OpenInfoPublishing" oi on mr.foiministryrequestid = oi.foiministryrequestid
		WHERE oi.publishingstatus = '%s' and mr.isactive = TRUE
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
			oi.openinfoid,
			mr.axisrequestid,
			oi.sitemap_pages,
			'unpublish' as type
		FROM public."OpenInfoPublishing" oi
		INNER JOIN public."FOIMinistryRequests" mr on oi.foiministryrequestid = mr.foiministryrequestid and mr.isactive = TRUE
		WHERE openinfostate = '%s' and publishingstatus != '%s'
	`, openstate_unpublish, openstatus_unpublish)

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

func UpdateOIRecordState(db *sql.DB, openinfoid int, publishingstatus string, message string, state string, sitemap_pages string) error {

	qry := `
		UPDATE public."OpenInfoPublishing"
		SET
			publishingstatus = $1,
			message = $2,
			openinfostate = $3,
			sitemap_pages = $4
		WHERE openinfoid = $5;
	`
	_, err := db.Exec(qry, publishingstatus, message, state, sitemap_pages, openinfoid)
	return err
}
