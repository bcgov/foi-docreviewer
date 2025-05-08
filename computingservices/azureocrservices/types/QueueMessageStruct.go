package types

type QueueMessage struct {
	MinistryRequestId int64  `json:"ministryRequestId"`
	RequestNumber     string `json:"requestNumber"`
	MinistryCode      string `json:"ministryCode"`
	DivisionName      string `json:"divisionName"`
	//ModifiedDate      string `json:"modifiedDate"`
	DocumentHashCode string `json:"documentHashCode"`
	S3Uri            string `json:"s3Uri"`
}
