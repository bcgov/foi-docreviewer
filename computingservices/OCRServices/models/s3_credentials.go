package models

type S3Credentials struct {
	S3AccessKey string `json:"s3accesskey"`
	S3SecretKey string `json:"s3secretkey"`
}
