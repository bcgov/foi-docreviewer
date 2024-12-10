package main

import (
	// "encoding/xml"
	"OpenInfoServices/lib/awslib"
	dbservice "OpenInfoServices/lib/db"
	envtool "OpenInfoServices/lib/env"
	redislib "OpenInfoServices/lib/queue"
	oiservices "OpenInfoServices/services"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	dateformat = "2006-01-02"
)

func main() {

	if len(os.Args) < 2 {
		fmt.Println("Please provide a parameter: dequeue, enqueue, sitemap or unpublish")
		return
	}

	// Set env from .env file for local testing
	// envtool.SetEnvFromFile()

	host := envtool.GetEnv("FOI_DB_HOST", "")
	port := envtool.GetEnv("FOI_DB_PORT", "")
	user := envtool.GetEnv("FOI_DB_USER", "")
	password := envtool.GetEnv("FOI_DB_PASSWORD", "")
	dbname := envtool.GetEnv("FOI_DB_NAME", "")
	queue := envtool.GetEnv("OI_QUEUE_NAME", "OpenInfoQueue")
	s3url := "https://" + envtool.GetEnv("OI_S3_HOST", "") + "/"
	oibucket := envtool.GetEnv("OI_S3_ENV", "dev") + "-" + envtool.GetEnv("OI_S3_BUCKET", "")
	oiprefix := envtool.GetEnv("OI_PREFIX", "")
	sitemapprefix := envtool.GetEnv("SITEMAP_PREFIX", "")
	// Convert the string to an integer
	sitemaplimit, strerr := strconv.Atoi(envtool.GetEnv("SITEMAP_PAGES_LIMIT", "5000"))
	if strerr != nil {
		log.Fatalf("Error converting string to int: %v", strerr)
		sitemaplimit = 5000
	}
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname)

	param := os.Args[1]

	switch param {
	case "dequeue":

		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		// Create a Redis client
		rdb := redislib.CreateRedisClient()
		// Define the queue name
		queueName := queue

		// Subscribe to the queue and read messages
		for {
			message, err := redislib.ReadMessage(rdb, queueName)
			if err != nil {
				if err == redis.Nil {
					fmt.Println("No messages in queue")
				} else {
					log.Fatalf("could not read message from queue: %v", err)
				}
				time.Sleep(1 * time.Second)
				continue
			}

			fmt.Printf("Message read from queue: %s\n", message)

			var msg oiservices.OpenInfoMessage
			err = json.Unmarshal([]byte(message), &msg)
			if err != nil {
				log.Fatalf("could not parse json string: %v", err)
				return
			}

			fmt.Printf("openinfoid: %d\n", msg.Openinfoid)
			fmt.Printf("foiministryrequestid: %d\n", msg.Foiministryrequestid)
			fmt.Printf("published_date: %s\n", msg.Published_date)
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", msg.Axisrequestid, msg.Description, msg.Published_date, msg.Contributor, msg.Applicant_type, msg.Fees)

			if msg.Type == "publish" {
				oiservices.Publish(msg, db)
			} else if msg.Type == "unpublish" {
				oiservices.Unpublish(msg, db)
			} else {
				fmt.Println("Unknown message type")
			}
		}

	case "enqueueforpublish":

		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		// Get the open info record, which are ready for publishing
		records, err := dbservice.GetOIRecordsForPrePublishing(db)
		if err != nil {
			log.Fatalf("%v", err)
			return
		}

		// Create a Redis client
		rdb := redislib.CreateRedisClient()

		// Define the queue name
		queueName := queue

		for _, item := range records {
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", item.Axisrequestid, item.Description, item.Published_date, item.Contributor, item.Applicant_type, item.Fees)

			jsonData, err := json.Marshal(item)
			if err != nil {
				panic(err)
			}

			// Write a message to the queue
			redislib.WriteMessage(rdb, queueName, string(jsonData))
		}

	case "enqueueforunpublish":
		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		// Get the open info record, which are ready for publishing
		records, err := dbservice.GetOIRecordsForUnpublishing(db)
		if err != nil {
			log.Fatalf("%v", err)
			return
		}

		// Create a Redis client
		rdb := redislib.CreateRedisClient()

		// Define the queue name
		queueName := queue

		for _, item := range records {
			fmt.Printf("ID: %s, Sitemap_Pages: %s, Type: %s\n", item.Axisrequestid, item.Sitemap_pages, item.Type)

			jsonData, err := json.Marshal(item)
			if err != nil {
				panic(err)
			}

			// Write a message to the queue
			redislib.WriteMessage(rdb, queueName, string(jsonData))
		}

	case "sitemap":

		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		// Get the open info record, which are ready for XML
		records, err := dbservice.GetOIRecordsForPublishing(db)
		if err != nil {
			log.Fatalf("%v", err)
			return
		}

		// Get the last sitemap_page from s3
		destBucket := oibucket
		destPrefix := sitemapprefix

		sitemapindex := awslib.ReadSiteMapIndexS3(destBucket, destPrefix, "sitemap_index.xml")
		urlset := awslib.ReadSiteMapPageS3(destBucket, destPrefix, "sitemap_pages_"+strconv.Itoa(len(sitemapindex.Sitemaps))+".xml")

		initialSitemapsCount := len(sitemapindex.Sitemaps)

		// Get the current time
		now := time.Now()
		lastMod := now.Format(dateformat)

		// Insert to XML
		for i, item := range records {
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", item.Axisrequestid, item.Description, item.Published_date, item.Contributor, item.Applicant_type, item.Fees)

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
				Loc:     s3url + destBucket + "/" + oiprefix + item.Axisrequestid + "/" + item.Axisrequestid + ".html",
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

		// Update openinfo table status & sitemap_pages file name to DB
		for _, item := range records {
			err = dbservice.UpdateOIRecordState(db, item.Openinfoid, "published", "added to sitemap", "Published", item.Sitemap_pages)
			if err != nil {
				log.Fatalf("%v", err)
				return
			}
		}

	case "test":
		//----- put testing script here -----

		// test unpublish
		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		// Create a Redis client
		rdb := redislib.CreateRedisClient()
		// Define the queue name
		queueName := queue

		// Subscribe to the queue and read messages
		message, err := redislib.ReadMessage(rdb, queueName)
		if err != nil {
			log.Fatalf("%v", err)
			return
		}

		fmt.Printf("Message read from queue: %s\n", message)

		var msg oiservices.OpenInfoMessage
		err = json.Unmarshal([]byte(message), &msg)
		if err != nil {
			log.Fatalf("could not parse json string: %v", err)
			return
		}

		fmt.Printf("openinfoid: %d\n", msg.Openinfoid)
		fmt.Printf("foiministryrequestid: %d\n", msg.Foiministryrequestid)
		fmt.Printf("published_date: %s\n", msg.Published_date)
		fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", msg.Axisrequestid, msg.Description, msg.Published_date, msg.Contributor, msg.Applicant_type, msg.Fees)

		oiservices.Unpublish(msg, db)

		//----- test script end -----

	default:
		fmt.Println("Unknown parameter. Please use 'dequeue', 'enqueueforpublish', 'sitemap' or 'enqueueforunpublish'")
	}

}
