package docreviewerocrservice

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"azureocrservice/logx"
	"azureocrservice/types"
	"azureocrservice/utils"
)

// PushtoDocReviewer posts one status row to the reviewer API. It never aborts
// the process: a failure is logged and reported as false so the caller decides.
func PushtoDocReviewer(docreviewAudit types.DocReviewAudit) bool {
	jsonData, err := json.Marshal(docreviewAudit)
	if err != nil {
		logx.Event("REVIEWER_POST_FAILED", "documentid", docreviewAudit.DocumentID, "status", docreviewAudit.Status, "err", err)
		return false
	}
	url := fmt.Sprintf("%v/api/documentocrjob", utils.ViperEnvVariable("docreviewerocrapiendpoint"))
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewBuffer(jsonData))
	if err != nil {
		logx.Event("REVIEWER_POST_FAILED", "documentid", docreviewAudit.DocumentID, "status", docreviewAudit.Status, "err", err)
		return false
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-FOI-OCR-Secret", utils.ViperEnvVariable("docreviewerocrapisecret"))

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		logx.Event("REVIEWER_POST_FAILED", "documentid", docreviewAudit.DocumentID, "status", docreviewAudit.Status, "err", err)
		return false
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusCreated || resp.StatusCode == http.StatusOK {
		logx.Event("REVIEWER_POST_OK", "documentid", docreviewAudit.DocumentID, "status", docreviewAudit.Status)
		return true
	}
	logx.Event("REVIEWER_POST_FAILED", "documentid", docreviewAudit.DocumentID, "status", docreviewAudit.Status, "httpstatus", resp.StatusCode)
	return false
}
