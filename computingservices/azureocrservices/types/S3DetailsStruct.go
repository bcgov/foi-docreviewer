package types

import "time"

type S3Details struct {
	EndPoint   string        `json:"endpoint"`
	AccessKey  string        `json:"accesskey"`
	SecretKey  string        `json:"secretkey"`
	BucketName string        `json:"bucketname"`
	ObjectKey  string        `json:"objectkey"`
	Region     string        `json:"region"`
	Expiry     time.Duration `json:"expiry"`
}
