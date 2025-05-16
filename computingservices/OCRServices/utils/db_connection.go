package utils

import (
	"database/sql"
	"fmt"
	"log"

	_ "github.com/lib/pq"
)

func GetDBConnection() *sql.DB {

	host := ViperEnvVariable("OCR_DB_HOST")
	port := ViperEnvVariable("OCR_DB_PORT")
	user := ViperEnvVariable("OCR_DB_USER")
	password := ViperEnvVariable("OCR_DB_PASSWORD")
	dbname := ViperEnvVariable("OCR_DB_NAME")

	psqlInfo := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname,
	)
	//fmt.Printf("psqlInfo:%v\n", psqlInfo)
	db, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		log.Fatalf("Error connecting to DB: %v", err)
	}
	return db
}
