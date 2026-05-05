package publish

import (
	"fmt"
	"strings"
	"time"

	"publication-service/internal/htmlindex"
	pub "publication-service/internal/publish"
)

func buildTemplateVars(d *Domain, res pub.CopyResult, publicURL string, now time.Time) htmlindex.TemplateVariables {
	base := strings.TrimRight(publicURL, "/") + "/" + d.Destination.Bucket + "/" + d.Destination.Prefix

	var letterLinks, otherLinks []htmlindex.Link
	var letterNames, letterSizes []string
	var fileNames, fileSizes []string

	for _, obj := range res.Objects {
		mb := fmt.Sprintf("%.2f", float64(obj.Size)/(1024*1024))
		lnk := htmlindex.Link{URL: base + obj.Key, FileName: obj.Key}
		if strings.HasPrefix(obj.Key, "Response_Letter_") {
			letterLinks = append(letterLinks, lnk)
			letterNames = append(letterNames, obj.Key)
			letterSizes = append(letterSizes, mb)
		} else {
			otherLinks = append(otherLinks, lnk)
			fileNames = append(fileNames, obj.Key)
			fileSizes = append(fileSizes, mb)
		}
	}

	htmlFile := d.RequestID + ".html"
	htmlURL := base + htmlFile

	allLinks := letterLinks
	allLinks = append(allLinks, otherLinks...)

	titlePrefix, subject := kindLabels(d.Kind)
	var metaTags []htmlindex.MetaTag
	reportPeriodArr := strings.Fields(d.ReportPeriod)
	if (d.Kind == pub.KindProactiveDisclosure) {
		metaTags := []htmlindex.MetaTag{
			{Name: "dc.title", Content: d.Contributor + " - " + d.Category + " - " + d.ReportPeriod},
			{Name: "dc.description", Content: generatePDDescription(d.Category, d.Contributor, d.ReportPeriod)}, 
			{Name: "high_level_subject", Content: d.Category},
			{Name: "dc.subject", Content: subject},
			{Name: "dc.published_date", Content: d.PublishedDate},
			{Name: "timestamp", Content: fmt.Sprintf("%d", now.Unix())},
			{Name: "dc.contributor", Content: d.Contributor},
			{Name: "recorduid", Content: d.RequestID},
			{Name: "recordurl", Content: htmlURL},
			{Name: "month", Content: generatePdMonth(reportPeriodArr)},
			{Name: "year", Content: generatePdYear(reportPeriodArr)},
			{Name: "letter", Content: ""},
			{Name: "letter_file_sizes", Content: ""},
			{Name: "notes", Content: ""},
			{Name: "notes_file_sizes", Content: ""},
			{Name: "files", Content: strings.Join(allFileNames, ",")},
			{Name: "file_sizes", Content: strings.Join(allFileSizes, ",")},
			{Name: "applicant_type", Content: ""},
			{Name: "fees", Content: ""},
			{Name: "position_title", Content: ""},
			{Name: "individual_name", Content: ""},
		}	
	} else {
		metaTags := []htmlindex.MetaTag{
			{Name: "dc.title", Content: titlePrefix + " - " + d.RequestID},
			{Name: "dc.description", Content: d.Description},
			{Name: "high_level_subject", Content: subject},
			{Name: "dc.subject", Content: subject},
			{Name: "dc.published_date", Content: d.PublishedDate},
			{Name: "timestamp", Content: fmt.Sprintf("%d", now.Unix())},
			{Name: "dc.contributor", Content: d.Contributor},
			{Name: "recorduid", Content: d.RequestID},
			{Name: "recordurl", Content: htmlURL},
			{Name: "month", Content: now.Format("01")},
			{Name: "year", Content: now.Format("2006")},
			{Name: "letter", Content: strings.Join(letterNames, ",")},
			{Name: "letter_file_sizes", Content: strings.Join(letterSizes, ",")},
			{Name: "notes", Content: ""},
			{Name: "notes_file_sizes", Content: ""},
			{Name: "files", Content: strings.Join(allFileNames, ",")},
			{Name: "file_sizes", Content: strings.Join(allFileSizes, ",")},
			{Name: "applicant_type", Content: d.ApplicantType},
			{Name: "fees", Content: fmt.Sprintf("$%.2f", float64(d.Fees)/100)},
			{Name: "position_title", Content: " "},
			{Name: "individual_name", Content: ""},
		}
	}

	return htmlindex.TemplateVariables{
		Title:    d.RequestID,
		MetaTags: metaTags,
		Links:    allLinks,
		Content:  titlePrefix + " - " + d.RequestID + " " + d.Description,
	}
}

func kindLabels(k pub.Kind) (titlePrefix, subject string) {
	switch k {
	case pub.KindProactiveDisclosure:
		return "Proactive Disclosure", "Proactive Disclosure"
	default:
		return "FOI Request", "FOI Request"
	}
}

func generatePDDescription(pdCategory, ministry, reportPeriod string) (string) {
	switch pdCategory {
	case "Direct Award Contracts":
		return fmt.Sprintf("This document is a summary of directly-awarded contracts for the %s for the time period of %d. ", ministry, reportPeriod)
	case "Calendars":
		return fmt.Sprintf("This document represents the calendars for the %s, for the time period of %d.", ministry, reportPeriod)
	case "Contracts over $10,000":
		return fmt.Sprintf("This document is a summary of contracts with values over $10,000 CAD for the %s for the time period of %d.", ministry, reportPeriod)
	case "Minister Quarterly Travel Expenses":
		return fmt.Sprintf("This document represents the Travel Expense report for the Minister of %s for the time period of %d.", ministry, reportPeriod)
	case "Estimates":
		return "Estimates notes prepared for the Minister."
	case "Transition Binders":
		return fmt.Sprintf("Transition Binder for %s, prepared for the incoming Minister.", ministry)
	case "Briefing Notes":
		return fmt.Sprintf("This document is a summary of Briefing Notes for the %s for the time period of %d.", ministry, reportPeriod)
	case "DM Travel Expenses":
		return fmt.Sprintf("This document represents the Travel Expense report for the Deputy Minister %s for the time period of %d.", ministry, reportPeriod)
	default:
		return ""
	}
}

func generatePdMonth(textArr []string) (int, error) {
	if textArr[0] == "Quarter" {
		quarter := textArr[1]
		switch quarter {
		case "1":
			return 4, nil
		case "2":
			return 7, nil
		case "3":
			return 10, nil
		case "4":
			return 1, nil
		}
	} else {
		t, err := time.Parse(textArr[0], month)
		if err != nil {
			return 0, err
		}
		return int(t.Month()), nil
	}
}

func generatePdYear(textArr []string) (string, err) {
	if (textArr[0] == "Quarter") {
		quarter := textArr[1]
		currentYear, nextYear, found := strings.Cut(textArr[2], "-")
		if !found {
			return "", fmt.Errorf("invalid format")
		}
		if quarter == "4" {
			return currentYear[:2] + nextYear
		}
		return currentYear
	} else {
		return textArr[1]
	}
}
