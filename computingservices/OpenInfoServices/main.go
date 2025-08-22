package main

import (
	// "encoding/xml"
	myconfig "OpenInfoServices/config"
	"OpenInfoServices/lib/awslib"
	dbservice "OpenInfoServices/lib/db"
	httpservice "OpenInfoServices/lib/http"
	redislib "OpenInfoServices/lib/queue"
	oiservices "OpenInfoServices/services"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/redis/go-redis/v9"
)

const (
	dateformat                 = "2006-01-02"
	openstatus_sitemap         = "ready for crawling"
	openstatus_sitemap_message = "sitemap ready"
	oistatus_published         = "Published"
)

var (
	//DB
	host     string
	port     string
	user     string
	password string
	dbname   string

	//Redis
	queue string

	//S3
	s3url         string
	oibucket      string
	oiprefix      string
	sitemapprefix string
	sitemaplimit  int

	//Others
	env        string
	foiflowapi string
)

func main() {
	//Only enable when running locally for using .env
	// setEnvForLocal(".env")

	fmt.Printf("Program started with %d arguments: %v\n", len(os.Args), os.Args)
	
	if len(os.Args) < 2 {
		fmt.Println("Please provide a parameter: dequeue, enqueue, sitemap or unpublish")
		os.Exit(1)
	}

	host, port, user, password, dbname = myconfig.GetDB()
	s3url, oibucket, oiprefix, sitemapprefix, sitemaplimit = myconfig.GetS3Path()
	env, queue, foiflowapi, _ = myconfig.GetOthers()

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
				if err != redis.Nil {
					log.Printf("could not read message from queue: %v", err)
				}
				Sleep(1 * time.Second)
				continue
			}

			fmt.Printf("Message read from queue: %s\n", message)

			var msg oiservices.OpenInfoMessage
			err = json.Unmarshal([]byte(message), &msg)
			if err != nil {
				log.Printf("could not parse json string: %v", err)
				continue
			}

			fmt.Printf("openinfoid: %d\n", msg.Openinfoid)
			fmt.Printf("foiministryrequestid: %d\n", msg.Foiministryrequestid)
			fmt.Printf("published_date: %s\n", msg.Published_date)
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v, Files: %v\n", msg.Axisrequestid, msg.Description, msg.Published_date, msg.Contributor, msg.Applicant_type, msg.Fees, msg.AdditionalFiles)

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
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v, Files: %v\n", item.Axisrequestid, item.Description, item.Published_date, item.Contributor, item.Applicant_type, item.Fees, item.Additionalfiles)

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
		fmt.Println("sitemap")

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

		fmt.Println("sitemap end")
	case "test":
		//----- put testing script here for manual test -----

		// ======== test unpublish
		// // Connect DB
		// db, err1 := dbservice.Conn(dsn)
		// if err1 != nil {
		// 	log.Fatalf("%v", err1)
		// 	return
		// }
		// defer db.Close()

		// // Create a Redis client
		// rdb := redislib.CreateRedisClient()
		// // Define the queue name
		// queueName := queue

		// // Subscribe to the queue and read messages
		// message, err := redislib.ReadMessage(rdb, queueName)
		// if err != nil {
		// 	log.Fatalf("%v", err)
		// 	return
		// }

		// fmt.Printf("Message read from queue: %s\n", message)

		// var msg oiservices.OpenInfoMessage
		// err = json.Unmarshal([]byte(message), &msg)
		// if err != nil {
		// 	log.Fatalf("could not parse json string: %v", err)
		// 	return
		// }

		// fmt.Printf("openinfoid: %d\n", msg.Openinfoid)
		// fmt.Printf("foiministryrequestid: %d\n", msg.Foiministryrequestid)
		// fmt.Printf("published_date: %s\n", msg.Published_date)
		// fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v\n", msg.Axisrequestid, msg.Description, msg.Published_date, msg.Contributor, msg.Applicant_type, msg.Fees)

		// oiservices.Unpublish(msg, db)

		// ========== test http
		// // Connect DB
		// db, err0 := dbservice.Conn(dsn)
		// if err0 != nil {
		// 	log.Fatalf("%v", err0)
		// 	return
		// }
		// defer db.Close()

		// fid, err := dbservice.GetFoirequestID(db, 1)
		// if err != nil {
		// 	log.Fatalf("Error: %v", err)
		// }
		// fmt.Printf("FOIRequestID: %d\n", fid)

		endpoint1 := fmt.Sprintf("%s/api/foiflow/programareas", foiflowapi)
		getResponse, err1 := httpservice.HttpGet(endpoint1)
		if err1 != nil {
			log.Fatalf("Failed to make GET call: %v", err1)
		}
		fmt.Printf("GET Response: %s\n", getResponse)

		// section := "oistatusid"
		// endpoint2 := fmt.Sprintf("%s/foirequests/%d/ministryrequest/%d/section/%s", foiflowapi, 1, 1, section)
		// postPayload := map[string]int{"oistatusid": 4}
		// postResponse, err2 := httpservice.HttpPost(endpoint2, postPayload)
		// if err2 != nil {
		// 	log.Fatalf("Failed to make POST call: %v", err2)
		// }
		// fmt.Printf("POST Response: %s\n", postResponse)

		//----- test script end -----

	default:
		fmt.Println("Unknown parameter. Please use 'dequeue', 'enqueueforpublish', 'sitemap' or 'enqueueforunpublish'")
	}
}

func JoinStr(a string, b string) (string, error) {
	if a == "" || b == "" {
		return "", errors.New("empty string")
	}
	return a + b, nil
}

func setEnvForLocal(path string) {
	absolutePath, err := filepath.Abs(path)
	if err != nil {
		log.Fatalf("failed to get absolute path: %v", err)
	}

	err = os.Setenv("ENVFILE_PATH", absolutePath)
	if err != nil {
		log.Fatalf("failed to set environment variable: %v", err)
	}
}
