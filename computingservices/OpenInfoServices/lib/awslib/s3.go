package awslib

import (
	myconfig "OpenInfoServices/config"
	"OpenInfoServices/lib/files"
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"path"
	"path/filepath"
	"strings"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	smithyendpoints "github.com/aws/smithy-go/endpoints"
)

var (
	//S3
	s3url         string
	oibucket      string
	oiprefix      string
	sitemapprefix string
	sitemaplimit  int
	region        string
	accessKey     string
	secretKey     string
	s3host        string
)

type ScanResult struct {
	LetterNames string
	LetterSizes string
	FileNames   string
	FileSizes   string
	Links       []files.Link
}

type SiteMap struct {
	XMLName xml.Name `xml:"sitemap"`
	Loc     string   `xml:"loc"`
	LastMod string   `xml:"lastmod"`
}

type SitemapIndex struct {
	XMLName  xml.Name  `xml:"sitemapindex"`
	Sitemaps []SiteMap `xml:"sitemap"`
}

type Url struct {
	XMLName xml.Name `xml:"url"`
	Loc     string   `xml:"loc"`
	LastMod string   `xml:"lastmod"`
}

type UrlSet struct {
	XMLName xml.Name `xml:"urlset"`
	Urls    []Url    `xml:"url"`
}

type AdditionalFile struct {
	Additionalfileid int    `json:"additionalfileid"`
	Filename         string `json:"filename"`
	S3uripath        string `json:"s3uripath"`
	Isactive         bool   `json:"isactive"`
}

type MimeTypes struct {
	Ext  string `json:"ext"`
	Type string `json:"type"`
}

type resolverV2 struct{}

func (*resolverV2) ResolveEndpoint(ctx context.Context, params s3.EndpointParameters) (
	smithyendpoints.Endpoint, error,
) {
	// s3.Options.BaseEndpoint is accessible here:
	// fmt.Printf("The endpoint provided in config is %s\n", *params.Endpoint)

	// fallback to default
	return s3.NewDefaultEndpointResolverV2().ResolveEndpoint(ctx, params)
}

// CreateS3Client creates and returns an S3 client
func CreateS3Client() *s3.Client {

	region, accessKey, secretKey, s3host := myconfig.GetS3()

	// Replace with your custom endpoint
	customEndpoint := "https://" + s3host + "/"

	// Load the AWS configuration with credentials
	tr := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
	}
	client := &http.Client{Transport: tr}
	cfg, err := config.LoadDefaultConfig(context.TODO(),
		config.WithHTTPClient(client),
		config.WithRegion(region),
		config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(accessKey, secretKey, "")),
	)
	if err != nil {
		log.Fatalf("unable to load SDK config, %v", err)
	}

	// Create an S3 service client
	return s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(customEndpoint)
		o.EndpointResolverV2 = &resolverV2{}
		o.UsePathStyle = true
	})
}

func ScanS3(openInfoBucket string, openInfoPrefix string, urlPrefix string, filemappings []AdditionalFile) (ScanResult, error) {
	bucket := openInfoBucket //"dev-openinfopub"
	prefix := openInfoPrefix //"poc/packages/HSG_2024_40515/" // Folder prefix in the bucket

	svc := CreateS3Client()

	// List objects in the bucket folder
	resp, errors := svc.ListObjectsV2(context.TODO(), &s3.ListObjectsV2Input{
		Bucket: aws.String(bucket),
		Prefix: aws.String(prefix),
	})
	if errors != nil {
		log.Fatalf("unable to list items in bucket %q, %v", bucket, errors)
	}

	var Result ScanResult
	var filePath string = ""
	var matched bool
	// var fileType string = "unknown"
	var err error
	var letterLinks []files.Link
	var fileLinks []files.Link

	// supportedFileTypes := []string{".pdf", ".xls", ".xlsx", ".csv", ".doc", ".docx", ".mp4", ".mp3", ".mpg", ".mpeg", ".avi", ".mov", ".wmv", ".wav"}

	// Print file information
	for _, item := range resp.Contents {

		filePath = *item.Key
		// fmt.Printf("*item.Key %v\n", *item.Key)

		// Get the file name
		base := path.Base(filePath)
		originalFileName, found, isactive := getOriginalName(filemappings, base)
		if found {
			if !isactive { // Skip over the deleted files (isactive = false)
				continue
			}
			base = originalFileName
		}
		// fmt.Printf("Base %s\n", base)
		// fmt.Printf("Name: %s, Size: %d bytes\n", filePath, *item.Size)

		// Find response letters
		patternResponseLetter := "Response_Letter_*.pdf"
		matched, err = filepath.Match(patternResponseLetter, base)
		if err != nil {
			log.Fatalf("error matching pattern, %v", err)
		}

		if matched {
			letterLinks = append(letterLinks, files.Link{FileName: base, URL: urlPrefix + base})
			if Result.LetterNames == "" {
				Result.LetterNames = base
				Result.LetterSizes = fmt.Sprintf("%.2f", (float64(*item.Size) / (1024 * 1024)))
			} else {
				Result.LetterNames = Result.LetterNames + "," + base
				Result.LetterSizes = Result.LetterSizes + "," + fmt.Sprintf("%.2f", (float64(*item.Size)/(1024*1024)))
			}
		} else {
			// Other files
			// fileType = getFileType(*item.Key)
			// if contains(supportedFileTypes, strings.ToLower(fileType)) {
			fileLinks = append(fileLinks, files.Link{FileName: base, URL: urlPrefix + base})
			if Result.FileNames == "" {
				Result.FileNames = base
				Result.FileSizes = fmt.Sprintf("%.2f", (float64(*item.Size) / (1024 * 1024)))
			} else {
				Result.FileNames = Result.FileNames + "," + base
				Result.FileSizes = Result.FileSizes + "," + fmt.Sprintf("%.2f", (float64(*item.Size)/(1024*1024)))
			}
			// }
		}
		Result.Links = append(letterLinks, fileLinks...)
	}

	// fmt.Printf("Combined letter names: %s, letter size: %s mb\n", Result.LetterNames, Result.LetterSizes)
	// fmt.Printf("Combined file names: %s, file size: %s mb\n", Result.FileNames, Result.FileSizes)
	return Result, errors
}

func CopyS3(sourceBucket string, sourcePrefix string, filemappings []AdditionalFile) {
	s3url, oibucket, oiprefix, sitemapprefix, sitemaplimit = myconfig.GetS3Path()
	env, _, _, mimetypesjson := myconfig.GetOthers()

	// bucket := "dev-openinfopub"
	bucket := sourceBucket
	prefix := sourcePrefix
	destBucket := oibucket
	destPrefix := oiprefix

	svc := CreateS3Client()

	// List objects in the bucket folder
	resp, err := svc.ListObjectsV2(context.TODO(), &s3.ListObjectsV2Input{
		Bucket: aws.String(bucket),
		Prefix: aws.String(prefix),
	})
	if err != nil {
		log.Fatalf("unable to list items in bucket %q, %v", bucket, err)
	}

	// Copy each object to the destination bucket
	for _, item := range resp.Contents {
		sourceKey := *item.Key

		// Get the file name
		base := path.Base(sourceKey)
		originalFileName, found, isactive := getOriginalName(filemappings, base)
		if found {
			if !isactive { // Skip over the deleted files (isactive = false)
				continue
			}
			base = originalFileName
		}
		// fmt.Printf("Base %s\n", base)
		// fmt.Printf("Name: %s, Size: %d bytes\n", filePath, *item.Size)

		// destKey := destPrefix + sourceKey[len(prefix):]
		destKey := destPrefix + strings.ReplaceAll(sourceKey, path.Base(sourceKey), base)

		// Determine the content type based on file extension
		var contentType string
		var mimetypes []MimeTypes
		if mimetypesjson != "" {
			json.Unmarshal([]byte(mimetypesjson), &mimetypes)
		}

		matched := false
		for _, mime := range mimetypes {
			if strings.EqualFold(filepath.Ext(bucket+"/"+sourceKey), mime.Ext) {
				contentType = mime.Type
				matched = true
				break
			}
		}

		if !matched {
			// Set default content type or leave it unset
			contentType = "application/octet-stream"
		}

		_, err := svc.CopyObject(context.TODO(), &s3.CopyObjectInput{
			Bucket:            aws.String(destBucket),
			CopySource:        aws.String(bucket + "/" + sourceKey),
			Key:               aws.String(destKey),
			ACL:               types.ObjectCannedACLPublicRead,
			ContentType:       aws.String(contentType),
			MetadataDirective: types.MetadataDirectiveReplace,
		})
		if err != nil {
			log.Fatalf("unable to copy item %q, %v", sourceKey, err)
		}

		fmt.Printf("Copied %s to %s\n", sourceKey, destKey)

		// // Ensure the copied object is publicly readable
		// _, err = svc.PutObjectAcl(context.TODO(), &s3.PutObjectAclInput{
		// 	Bucket: aws.String(destBucket),
		// 	Key:    aws.String(destKey),
		// 	ACL:    types.ObjectCannedACLPublicRead,
		// })
		// if err != nil {
		// 	fmt.Println("Error setting object ACL:", err)
		// 	return
		// }
	}

	fmt.Println("All files copied successfully!")
}

func SaveFileS3(openInfoBucket string, openInfoPrefix string, filename string, buf []byte) error {
	bucket := openInfoBucket //"dev-openinfopub"
	prefix := openInfoPrefix //"poc/packages/HSG_2024_40515/" // Folder prefix in the bucket

	svc := CreateS3Client()

	// Upload the HTML content to S3
	_, err := svc.PutObject(context.TODO(), &s3.PutObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(prefix + filename),
		Body:   bytes.NewReader(buf),
	})
	if err != nil {
		fmt.Println("Error uploading file:", err)
	} else {
		fmt.Println("File uploaded successfully!")
	}

	return err
}

func SaveHTMLS3(openInfoBucket string, openInfoPrefix string, filename string, buf []byte) error {
	bucket := openInfoBucket //"dev-openinfopub"
	prefix := openInfoPrefix //"poc/packages/HSG_2024_40515/" // Folder prefix in the bucket

	svc := CreateS3Client()

	// Upload the HTML content to S3
	_, err := svc.PutObject(context.TODO(), &s3.PutObjectInput{
		Bucket:      aws.String(bucket),
		Key:         aws.String(prefix + filename),
		Body:        bytes.NewReader(buf),
		ContentType: aws.String("text/html"),
	})
	if err != nil {
		fmt.Println("Error uploading file:", err)
	} else {
		fmt.Println("File uploaded successfully!")
	}

	return err
}

func SaveXMLS3(openInfoBucket string, openInfoPrefix string, filename string, buf []byte) error {
	bucket := openInfoBucket //"dev-openinfopub"
	prefix := openInfoPrefix //"poc/packages/HSG_2024_40515/" // Folder prefix in the bucket

	svc := CreateS3Client()

	// Upload the HTML content to S3
	_, err := svc.PutObject(context.TODO(), &s3.PutObjectInput{
		Bucket:             aws.String(bucket),
		Key:                aws.String(prefix + filename),
		Body:               bytes.NewReader(buf),
		ContentType:        aws.String("application/xml"),
		ContentDisposition: aws.String("inline"),
		ACL:                types.ObjectCannedACLPublicRead,
	})
	if err != nil {
		fmt.Println("Error uploading file:", err)
	} else {
		fmt.Println("XML File uploaded successfully!")
	}

	return err
}

func GetFileFromS3(openInfoBucket string, openInfoPrefix string, filename string) *s3.GetObjectOutput {
	bucket := openInfoBucket //"dev-openinfopub"
	prefix := openInfoPrefix //"poc/packages/HSG_2024_40515/" // Folder prefix in the bucket

	svc := CreateS3Client()

	// Download the XML file from S3
	result, err := svc.GetObject(context.TODO(), &s3.GetObjectInput{
		Bucket: aws.String(bucket),
		Key:    aws.String(prefix + filename),
	})
	if err != nil {
		panic(err)
	}
	// defer result.Body.Close()

	return result
}

func ReadSiteMapIndexS3(openInfoBucket string, openInfoPrefix string, filename string) SitemapIndex {
	result := GetFileFromS3(openInfoBucket, openInfoPrefix, filename)
	defer result.Body.Close()

	// Parse the XML content
	var sitemapindex SitemapIndex
	err := xml.NewDecoder(result.Body).Decode(&sitemapindex)
	if err != nil {
		panic(err)
	}

	return sitemapindex
}

func ReadSiteMapPageS3(openInfoBucket string, openInfoPrefix string, filename string) UrlSet {
	result := GetFileFromS3(openInfoBucket, openInfoPrefix, filename)
	defer result.Body.Close()

	// Parse the XML content
	var urlset UrlSet
	err := xml.NewDecoder(result.Body).Decode(&urlset)
	if err != nil {
		panic(err)
	}

	return urlset
}

func SaveSiteMapIndexS3(openInfoBucket string, openInfoPrefix string, filename string, updatedsitemapindex SitemapIndex) error {
	// Serialize the updated XML
	updatedXML, err := xml.MarshalIndent(updatedsitemapindex, "", "  ")
	if err != nil {
		panic(err)
	}

	// Add the XML header and xmlns attribute
	xmlHeader := []byte(xml.Header)
	xmlns := []byte(` xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`)
	updatedXML = append(xmlHeader, updatedXML...)
	updatedXML = bytes.Replace(updatedXML, []byte("<sitemapindex>"), []byte("<sitemapindex"+string(xmlns)+">"), 1)

	return SaveXMLS3(openInfoBucket, openInfoPrefix, filename, updatedXML)
}

func SaveSiteMapPageS3(openInfoBucket string, openInfoPrefix string, filename string, updatedurlset UrlSet) error {
	// Serialize the updated XML
	updatedXML, err := xml.MarshalIndent(updatedurlset, "", "  ")
	if err != nil {
		panic(err)
	}

	// Add the XML header and xmlns attribute
	xmlHeader := []byte(xml.Header)
	xmlns := []byte(` xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"`)
	updatedXML = append(xmlHeader, updatedXML...)
	updatedXML = bytes.Replace(updatedXML, []byte("<urlset>"), []byte("<urlset"+string(xmlns)+">"), 1)

	return SaveXMLS3(openInfoBucket, openInfoPrefix, filename, updatedXML)
}

func RemoveFromS3(openInfoBucket string, openInfoPrefix string) error {

	svc := CreateS3Client()

	// Upload the HTML content to S3
	_, err := svc.DeleteObject(context.TODO(), &s3.DeleteObjectInput{
		Bucket: aws.String(openInfoBucket),
		Key:    aws.String(openInfoPrefix),
	})
	if err != nil {
		fmt.Println("Error removing file:", err)
	} else {
		fmt.Println("File removed successfully!")
	}

	return err
}

func RemoveFolderFromS3(openInfoBucket string, openInfoPrefix string) error {

	svc := CreateS3Client()

	// List objects in the folder
	resp, err := svc.ListObjectsV2(context.TODO(), &s3.ListObjectsV2Input{
		Bucket: aws.String(openInfoBucket),
		Prefix: aws.String(openInfoPrefix),
	})
	if err != nil {
		return fmt.Errorf("unable to list items in bucket %q, %w", openInfoBucket, err)
	}

	// Delete each object in the folder
	for _, item := range resp.Contents {
		_, err := svc.DeleteObject(context.TODO(), &s3.DeleteObjectInput{
			Bucket: aws.String(openInfoBucket),
			Key:    aws.String(*item.Key),
		})
		if err != nil {
			log.Fatalf("unable to delete item %q, %v", *item.Key, err)
		}
		fmt.Printf("Deleted %s\n", *item.Key)
	}

	fmt.Println("Folder and its contents deleted successfully!")
	return err
}

func getFileType(filePath string) string {
	// Get the file extension
	ext := filepath.Ext(filePath)
	if ext == "" {
		return "unknown"
	}

	return ext
}

// Function to check if a string array contains a specific string
func contains(arr []string, str string) bool {
	for _, v := range arr {
		if v == str {
			return true
		}
	}
	return false
}

// Get Original Filename
func getOriginalName(filemappings []AdditionalFile, key string) (string, bool, bool) {
	for _, item := range filemappings {
		// Parse the URL
		parsedURL, err := url.Parse(item.S3uripath)
		if err != nil {
			fmt.Printf("Error parsing URL: %v\n", err)
			continue
		}

		// Extract the path
		urlPath := parsedURL.Path

		// Get the base (last segment) of the path
		base := path.Base(urlPath)

		if base == key {
			return item.Filename, true, item.Isactive
		}
	}
	return "", false, true
}
