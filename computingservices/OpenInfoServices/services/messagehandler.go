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
)

type OpenInfoMessage struct {
	Openinfoid           int                     `json:"openinfoid, omitempty"`
	Foiministryrequestid int                     `json:"foiministryrequestid"`
	Foirequestid         int                     `json:"foirequestid"`
	Axisrequestid        string                  `json:"axisrequestid"`
	Description          string                  `json:"description"`
	Published_date       string                  `json:"published_date"`
	Contributor          string                  `json:"contributor, omitempty"`
	Applicant_type       string                  `json:"applicant_type, omitempty"`
	Fees                 float32                 `json:"fees, omitempty"`
	BCgovcode            string                  `json:"bcgovcode"`
	Type                 string                  `json:"type"`
	Sitemap_pages        string                  `json:"sitemap_pages"`
	AdditionalFiles      []awslib.AdditionalFile `json:"additionalfiles"`
	Proactivedisclosureid int                     `json:"pdfoiid, omitempty"`
	PDcategory           string                  `json:"pdcategory, omitempty"`
	Positiontitle		string                  `json:"positiontitle, omitempty"`
	Individualname		string                  `json:"individualname, omitempty"`
	Ministry			string                  `json:"ministry, omitempty"`
	Stockexplanation		string                  `json:"stockexplanation, omitempty"`
}

var (
	//S3
	s3url         string
	oibucket      string
	oiprefix      string
	sitemapprefix string

	env string
)

func Publish(msg OpenInfoMessage, db *sql.DB) {

	s3url, oibucket, oiprefix, sitemapprefix, _ = myconfig.GetS3Path()
	env, _, _, _ = myconfig.GetOthers()

	oibucket := env + "-" + oibucket

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

	//Set up base meta tags
	metaTags := []files.MetaTag{
		{Name: "dc.description", Content: msg.Description},
		{Name: "timestamp", Content: fmt.Sprintf("%d", unixTimestamp)},
		{Name: "recorduid", Content: msg.Axisrequestid},
		{Name: "recordurl", Content: s3url + oibucket + "/" + oiprefix + msg.Axisrequestid + "/openinfo/" + msg.Axisrequestid + ".html"},
		{Name: "letter", Content: result.LetterNames},
		{Name: "letter_file_sizes", Content: result.LetterSizes},
		{Name: "files", Content: result.FileNames},
		{Name: "file_sizes", Content: result.FileSizes},
	}

	// Build meta tags based on PD category
	switch msg.PDcategory {
	case "calendar":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Minister Calendar - " + msg.Axisrequestid},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "position_title", Content: msg.Positiontitle},
			files.MetaTag{Name: "individual_name", Content: msg.Individualname},
			files.MetaTag{Name: "stock_explanation", Content: msg.Stockexplanation},
			files.MetaTag{Name: "high_level_subject", Content: "Calendar"},
			files.MetaTag{Name: "dc.subject", Content: "Calendar"},
		)
	case "deputyMinisterTravel":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Deputy Minister Travel - " + msg.Axisrequestid},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "position_title", Content: msg.Positiontitle},
			files.MetaTag{Name: "individual_name", Content: msg.Individualname},
			files.MetaTag{Name: "stock_explanation", Content: msg.Stockexplanation},
			files.MetaTag{Name: "high_level_subject", Content: "Deputy Minister Travel"},
			files.MetaTag{Name: "dc.subject", Content: "Deputy Minister Travel"},
		)
	case "ministerTravel":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Minister Travel - " + msg.Axisrequestid},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "position_title", Content: msg.Positiontitle},
			files.MetaTag{Name: "individual_name", Content: msg.Individualname},
			files.MetaTag{Name: "stock_explanation", Content: msg.Stockexplanation},
			files.MetaTag{Name: "high_level_subject", Content: "Minister Travel"},
			files.MetaTag{Name: "dc.subject", Content: "Minister Travel"},
		)
	case "briefingNotes":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Briefing Notes - " + msg.Axisrequestid},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "month", Content: now.Format(dateformat_month)},
			files.MetaTag{Name: "year", Content: now.Format(dateformat_year)},
			files.MetaTag{Name: "high_level_subject", Content: "Briefing Notes"},
			files.MetaTag{Name: "dc.subject", Content: "Briefing Notes"},
		)
	case "directlyAwardedContracts":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Directly Awarded Contracts - " + msg.Axisrequestid},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "stock_explanation", Content: msg.Stockexplanation},
			files.MetaTag{Name: "high_level_subject", Content: "Directly Awarded Contracts"},
			files.MetaTag{Name: "dc.subject", Content: "Directly Awarded Contracts"},
		)
	case "contractsOver10k":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Contracts Over 10k - " + msg.Axisrequestid},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "stock_explanation", Content: msg.Stockexplanation},
			files.MetaTag{Name: "high_level_subject", Content: "Contracts Over 10k"},
			files.MetaTag{Name: "dc.subject", Content: "Contracts Over 10k"},
		)
	case "estimatesNotes":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Estimates Notes - " + msg.Axisrequestid},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "high_level_subject", Content: "Estimates Notes"},
			files.MetaTag{Name: "dc.subject", Content: "Estimates Notes"},
		)
	case "transitionBinders":
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "Transition Binders - " + msg.Axisrequestid},
			files.MetaTag{Name: "ministry", Content: msg.Ministry},
			files.MetaTag{Name: "high_level_subject", Content: "Transition Binders"},
			files.MetaTag{Name: "dc.subject", Content: "Transition Binders"},
		)
	default:
		// If no specific PD category is set, use the default OI meta tags
		metaTags = append(metaTags,
			files.MetaTag{Name: "dc.title", Content: "FOI Request - " + msg.Axisrequestid},
			files.MetaTag{Name: "high_level_subject", Content: "FOI Request"},
			files.MetaTag{Name: "dc.subject", Content: "FOI Request"},
			files.MetaTag{Name: "dc.published_date", Content: msg.Published_date},
			files.MetaTag{Name: "dc.contributor", Content: msg.Contributor},
			files.MetaTag{Name: "month", Content: now.Format(dateformat_month)},
			files.MetaTag{Name: "year", Content: now.Format(dateformat_year)},
			files.MetaTag{Name: "notes", Content: ""},
			files.MetaTag{Name: "notes_file_sizes", Content: ""},
			files.MetaTag{Name: "fees", Content: fmt.Sprintf("$%.2f", msg.Fees)},
			files.MetaTag{Name: "applicant_type", Content: msg.Applicant_type},
			files.MetaTag{Name: "position_title", Content: " "},
			files.MetaTag{Name: "individual_name", Content: ""},
		)
	}

	// Define the data to be passed to the template
	variables := files.TemplateVariables{
		Title: msg.Axisrequestid,
		MetaTags: metaTags,
		Links:   result.Links,
		Content: getOIContentLabel(msg.PDcategory, msg.Axisrequestid, msg.Description),
	}

	buf := files.CreateHTML(variables)
	err = awslib.SaveHTMLS3(msg.BCgovcode+"-"+env+"-e", msg.Axisrequestid+"/openinfo/", msg.Axisrequestid+".html", buf.Bytes())
	if err != nil {
		log.Fatalf("%v", err)
		return
	}

	// Copy files to open info bucket
	awslib.CopyS3(msg.BCgovcode+"-"+env+"-e", msg.Axisrequestid+"/openinfo/", msg.AdditionalFiles)

	// Update open info or proactive disclosure status in DB
	var err error
	if msg.Proactivedisclosureid != 0 {
		err = dbservice.UpdatePDRecordStatus(db, msg.Foiministryrequestid, openstatus_ready, openstatus_ready_message)
	} else {
		err = dbservice.UpdateOIRecordStatus(db, msg.Foiministryrequestid, openstatus_ready, openstatus_ready_message)
	}
	if err != nil {
		log.Fatalf("%v", err)
		return
	}
}

func Unpublish(msg OpenInfoMessage, db *sql.DB) {
	// Remove folder from s3

	s3url, oibucket, oiprefix, sitemapprefix, _ = myconfig.GetS3Path()
	env, _, _, _ = myconfig.GetOthers()

	destBucket := env + "-" + oibucket
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

	// Update unpublish status to DB for oi and proactive disclosure
	var err error
	if msg.Proactivedisclosureid != 0 {
		err = dbservice.UpdatePDRecordStatus(db, msg.Foiministryrequestid, openstatus_unpublish, openstatus_unpublish_message)
	} else {
		err = dbservice.UpdateOIRecordStatus(db, msg.Foiministryrequestid, openstatus_unpublish, openstatus_unpublish_message)
	}
	if err != nil {
		log.Fatalf("%v", err)
		return
	}
}

func getOIContentLabel(pdCategory, axisID, description string) string {
	var title string
    switch pdCategory {
    case "calendar":
        title = "Minister Calendar - " + axisID
    case "deputyMinisterTravel":
        title = "Deputy Minister Travel - " + axisID
    case "ministerTravel":
        title = "Minister Travel - " + axisID
    case "briefingNotes":
        title = "Briefing Notes - " + axisID
    case "directlyAwardedContracts":
        title = "Directly Awarded Contracts - " + axisID
    case "contractsOver10k":
        title = "Contracts Over 10k - " + axisID
    case "estimatesNotes":
        title = "Estimates Notes - " + axisID
    case "transitionBinders":
        title = "Transition Binders - " + axisID
    default:
        title = "FOI Request - " + axisID
    }
	return title + " " + msg.Description
}
