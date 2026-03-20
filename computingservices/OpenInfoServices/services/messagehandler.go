package oiservices

import (
	// "encoding/xml"
	myconfig "OpenInfoServices/config"
	"OpenInfoServices/lib/awslib"
	dbservice "OpenInfoServices/lib/db"
	"OpenInfoServices/lib/files"
	"database/sql"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"
)

const (
	dateformat                   = "2006-01-02"
	dateformat_month             = "01"
	dateformat_year              = "2006"
	openstatus_ready             = "ready for sitemap"
	openstatus_ready_message     = "html ready"
	openstatus_unpublish         = "unpublished"
	openstatus_unpublish_message = "entry removed from sitemap"
	openstatus_sitemap           = "ready for crawling"
	openstatus_sitemap_message   = "sitemap ready"
	oistatus_published           = "Published"
)

type OpenInfoMessage struct {
	Openinfoid           int                     `json:"openinfoid"`
	Foiministryrequestid int                     `json:"foiministryrequestid"`
	Foirequestid         int                     `json:"foirequestid"`
	Axisrequestid        string                  `json:"axisrequestid"`
	Description          string                  `json:"description"`
	Published_date       string                  `json:"published_date"`
	Contributor          string                  `json:"contributor"`
	Applicant_type       string                  `json:"applicant_type"`
	Fees                 float32                 `json:"fees"`
	BCgovcode            string                  `json:"bcgovcode"`
	Type                 string                  `json:"type"`
	Sitemap_pages        string                  `json:"sitemap_pages"`
	AdditionalFiles      []awslib.AdditionalFile `json:"additionalfiles"`
}

var (
	//S3
	s3url         string
	oibucket      string
	oiprefix      string
	sitemapprefix string
	sitemaplimit  int

	env        string
	foiflowapi string
)

func Publish(msg OpenInfoMessage, db *sql.DB) {

	s3url, oibucket, oiprefix, sitemapprefix, _ = myconfig.GetS3Path()
	env, _, _, _ = myconfig.GetOthers()

	if env != "" {
		oibucket = env + "-" + oibucket
	}

	// Get file info from s3 bucket folder
	var result awslib.ScanResult
	result, err := awslib.ScanS3(msg.BCgovcode+"-"+env+"-e", msg.Axisrequestid+"/openinfo/", s3url+oibucket+"/"+oiprefix+msg.Axisrequestid+"/openinfo/", msg.AdditionalFiles)
	if err != nil {
		log.Fatalf("%v", err)
		return
	}
	fmt.Printf("Combined letter names: %s, letter size: %s mb\n", result.LetterNames, result.LetterSizes)
	fmt.Printf("Combined file names: %s, file size: %s mb\n", result.FileNames, result.FileSizes)

	// Get the current time
	now := time.Now()
	// Get the Unix timestamp
	unixTimestamp := now.Unix()

	// Define the data to be passed to the template
	variables := files.TemplateVariables{
		Title: msg.Axisrequestid,
		MetaTags: []files.MetaTag{
			{Name: "dc.title", Content: "FOI Request - " + msg.Axisrequestid},
			{Name: "dc.description", Content: msg.Description},
			{Name: "high_level_subject", Content: "FOI Request"},
			{Name: "dc.subject", Content: "FOI Request"},
			{Name: "dc.published_date", Content: msg.Published_date},
			{Name: "timestamp", Content: fmt.Sprintf("%d", unixTimestamp)},
			{Name: "dc.contributor", Content: msg.Contributor},
			{Name: "recorduid", Content: msg.Axisrequestid},
			{Name: "recordurl", Content: s3url + oibucket + "/" + oiprefix + msg.Axisrequestid + "/openinfo/" + msg.Axisrequestid + ".html"},
			{Name: "month", Content: now.Format(dateformat_month)},
			{Name: "year", Content: now.Format(dateformat_year)},
			{Name: "letter", Content: result.LetterNames},
			{Name: "letter_file_sizes", Content: result.LetterSizes},
			{Name: "notes", Content: ""},
			{Name: "notes_file_sizes", Content: ""},
			{Name: "files", Content: result.FileNames},
			{Name: "file_sizes", Content: result.FileSizes},
			{Name: "applicant_type", Content: msg.Applicant_type},
			{Name: "fees", Content: fmt.Sprintf("$%.2f", msg.Fees)},
			{Name: "position_title", Content: " "},
			{Name: "individual_name", Content: ""},
		},
		Links:   result.Links,
		Content: "FOI Request - " + msg.Axisrequestid + " " + msg.Description,
	}

	buf := files.CreateHTML(variables)
	err = awslib.SaveHTMLS3(msg.BCgovcode+"-"+env+"-e", msg.Axisrequestid+"/openinfo/", msg.Axisrequestid+".html", buf.Bytes())
	if err != nil {
		log.Fatalf("%v", err)
		return
	}

	// Copy files to open info bucket
	awslib.CopyS3(msg.BCgovcode+"-"+env+"-e", msg.Axisrequestid+"/openinfo/", msg.AdditionalFiles)

	// Update open info status in DB
	err = dbservice.UpdateOIRecordStatus(db, msg.Foiministryrequestid, openstatus_ready, openstatus_ready_message)
	if err != nil {
		log.Fatalf("%v", err)
		return
	}

	fmt.Println("sitemap")
	UpdateSitemap(db)
	fmt.Println("sitemap end")
}

func PublishNow(msg OpenInfoMessage, db *sql.DB) {

	Publish(msg, db)

	fmt.Println("sitemap")
	UpdateSitemap(db)
	fmt.Println("sitemap end")
}

func Unpublish(msg OpenInfoMessage, db *sql.DB) {
	// Remove folder from s3

	s3url, oibucket, oiprefix, sitemapprefix, _ = myconfig.GetS3Path()
	env, _, _, _ = myconfig.GetOthers()

	destBucket := oibucket
	if env != "" {
		destBucket = env + "-" + oibucket
	}
	destPrefix := oiprefix
	err := awslib.RemoveFolderFromS3(destBucket, destPrefix+msg.Axisrequestid+"/") // Add a trailing slash to delete the folder
	if err != nil {
		log.Fatalf("%v", err)
		return
	}

	if msg.Sitemap_pages != "" {
		// Remove entry from sitemap_pages_.xml

		// 1. get the last sitemap_page from s3
		prefix := sitemapprefix
		urlset := awslib.ReadSiteMapPageS3(destBucket, prefix, msg.Sitemap_pages)

		// 2. find the index of the target entry
		index := -1
		for i, item := range urlset.Urls {
			if strings.Contains(item.Loc, msg.Axisrequestid) {
				index = i
				break
			}
		}

		// 3. remove entry from the array
		if index != -1 {
			urlset.Urls = append(urlset.Urls[:index], urlset.Urls[index+1:]...)
			fmt.Println("Entry removed:", msg.Axisrequestid)
		} else {
			fmt.Println("Entry not found", msg.Axisrequestid)
		}

		// 4. save sitemap_pages_.xml
		err = awslib.SaveSiteMapPageS3(destBucket, prefix, msg.Sitemap_pages, urlset)
		if err != nil {
			log.Fatalf("failed to save "+msg.Sitemap_pages+": %v", err)
			return
		}
	}

	// Update unpublish status to DB
	err = dbservice.UpdateOIRecordStatus(db, msg.Foiministryrequestid, openstatus_unpublish, openstatus_unpublish_message)
	if err != nil {
		log.Fatalf("%v", err)
		return
	}
}

func UpdateSitemap(db *sql.DB) {
	fmt.Println("sitemap")

	// Get the open info record, which are ready for XML
	records, err := dbservice.GetOIRecordsForPublishing(db)
	if err != nil {
		log.Fatalf("%v", err)
		return
	}

	// Get the last sitemap_page from s3
	destBucket := oibucket
	if env != "" {
		destBucket = env + "-" + oibucket
	}
	destPrefix := sitemapprefix

	sitemapindex := awslib.ReadSiteMapIndexS3(destBucket, destPrefix, "sitemap_index.xml")
	urlset := awslib.ReadSiteMapPageS3(destBucket, destPrefix, "sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml")

	initialSitemapsCount := len(sitemapindex.Sitemaps)

	// Get the current time
	now := time.Now()
	lastMod := now.Format(dateformat)

	fmt.Printf("Records: %v\n", records)
	// time.Sleep(60 * time.Second)

	// Insert to XML
	for i, item := range records {
		fmt.Printf("main - ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", item.Axisrequestid, item.Description, item.Published_date, item.Contributor, item.Applicant_type, item.Fees)

		// Save sitemap_pages_.xml which reached 5000 limit
		if len(urlset.Urls) >= sitemaplimit {
			// Save sitemap_pages_.xml
			err = awslib.SaveSiteMapPageS3(destBucket, destPrefix, "sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml", urlset)
			if err != nil {
				log.Fatalf("failed to save sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml: %v", err)
				return
			}

			// Update sitemap index
			sitemap := awslib.SiteMap{
				Loc:     s3url + destBucket + "/" + destPrefix + "sitemap_pages_" + strconv.Itoa(len(sitemapindex.Sitemaps)+1) + ".xml",
				LastMod: lastMod,
			}
			sitemapindex.Sitemaps = append(sitemapindex.Sitemaps, sitemap)

			// Clear urlset for entries already saved into sitemap_pages
			urlset.Urls = []awslib.Url{}
		}

		url := awslib.Url{
			Loc:     s3url + destBucket + "/" + oiprefix + item.Axisrequestid + "/openinfo/" + item.Axisrequestid + ".html",
			LastMod: lastMod,
		}
		urlset.Urls = append(urlset.Urls, url)

		// Save sitemap_pages file name
		records[i].Sitemap_pages = "sitemap_pages_" + strconv.Itoa(len(sitemapindex.Sitemaps)) + ".xml"
	}

	// Save new entries to sitemap_pages_.xml
	err = awslib.SaveSiteMapPageS3(destBucket, destPrefix, "sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml", urlset)
	if err != nil {
		log.Fatalf("failed to save sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml: %v", err)
		return
	}

	// Update sitemap_index.xml if there are new sitemap_pages_.xml created
	if len(sitemapindex.Sitemaps) > initialSitemapsCount {
		err = awslib.SaveSiteMapIndexS3(destBucket, destPrefix, "sitemap_index.xml", sitemapindex)
		if err != nil {
			log.Fatalf("failed to save sitemap_index.xml: %v", err)
			return
		}
	}

	// Retrieve oipublicationstatus_id based on oistatus
	var oistatusid int
	err = db.QueryRow(`SELECT oistatusid FROM public."OpenInformationStatuses" WHERE name = $1 and isactive = TRUE`, oistatus_published).Scan(&oistatusid)
	if err != nil {
		log.Fatalf("Error retrieving oistatusid: %v", err)
	}

	// Update openinfo table status & sitemap_pages file name to DB
	for _, item := range records {
		err = dbservice.UpdateOIRecordState(db, foiflowapi, item.Foiministryrequestid, item.Foirequestid, openstatus_sitemap, openstatus_sitemap_message, item.Sitemap_pages, oistatusid)
		if err != nil {
			log.Fatalf("failed to update OI state: %v", err)
			return
		}
	}
}
