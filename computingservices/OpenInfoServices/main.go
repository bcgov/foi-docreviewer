package main

import (
	// "encoding/xml"
	myconfig "OpenInfoServices/config"
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
				time.Sleep(1 * time.Second)
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
			fmt.Printf("proactivedisclosureid: %d\n", msg.Proactivedisclosureid)
			fmt.Printf("foiministryrequestid: %d\n", msg.Foiministryrequestid)
			fmt.Printf("published_date: %s\n", msg.Published_date)
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v, Files: %v, Category: %s\n", msg.Axisrequestid, msg.Description, msg.Published_date, msg.Contributor, msg.Applicant_type, msg.Fees, msg.AdditionalFiles, msg.Proactivedisclosurecategory)

			switch msg.Type {
			case "publish":
				oiservices.Publish(msg, db)
			case "unpublish":
				oiservices.Unpublish(msg, db)
			case "publishnow":
				oiservices.PublishNow(msg, db)
			default:
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

		// Get proactive disclosure record, which are ready for publishing
		pdrecords, err := dbservice.GetPDOIRecordsForPrePublishing(db)
		if err != nil {
			log.Fatalf("%v", err)
			return
		}

		for _, item := range pdrecords {
			fmt.Printf("ID: %s, Description: %s, Published Date: %s, Contributor: %s, Applicant Type: %s, Fees: %v, Files: %v, Category: %s\n", item.Axisrequestid, item.Description, item.Published_date, item.Contributor, item.Applicant_type, item.Fees, item.Additionalfiles, item.Proactivedisclosurecategory)

			jsonData, err := json.Marshal(item)
			if err != nil {
				panic(err)
			}

			// Write a message to the queue
			redislib.WriteMessage(rdb, queueName, string(jsonData))
		}

	// case "enqueueforunpublish":
	// 	//------------ Can remove this cronjob/case now. Replaced by unpublish API endpoint -----------

	// 	// Connect DB
	// 	db, err1 := dbservice.Conn(dsn)
	// 	if err1 != nil {
	// 		log.Fatalf("%v", err1)
	// 		return
	// 	}
	// 	defer db.Close()

	// 	// Get the open info record, which are ready for publishing
	// 	records, err := dbservice.GetOIRecordsForUnpublishing(db)
	// 	if err != nil {
	// 		log.Fatalf("%v", err)
	// 		return
	// 	}

	// 	// Create a Redis client
	// 	rdb := redislib.CreateRedisClient()

	// 	// Define the queue name
	// 	queueName := queue

	// 	for _, item := range records {
	// 		fmt.Printf("ID: %s, Sitemap_Pages: %s, Type: %s\n", item.Axisrequestid, item.Sitemap_pages, item.Type)

	// 		jsonData, err := json.Marshal(item)
	// 		if err != nil {
	// 			panic(err)
	// 		}

	// 		// Write a message to the queue
	// 		redislib.WriteMessage(rdb, queueName, string(jsonData))
	// 	}

	case "sitemap":
		fmt.Println("sitemap")

		// Connect DB
		db, err1 := dbservice.Conn(dsn)
		if err1 != nil {
			log.Fatalf("%v", err1)
			return
		}
		defer db.Close()

		oiservices.UpdateSitemap(db)
		oiservices.UpdatePDSitemap(db)

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
