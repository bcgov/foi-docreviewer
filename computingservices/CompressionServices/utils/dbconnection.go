package utils

import (
	"database/sql"
	"fmt"
	"log"

	_ "github.com/lib/pq"
)

func GetDBConnection() *sql.DB {
	//cfg := LoadConfig()

	host := ViperEnvVariable("COMPRESSION_DB_HOST")
	port := ViperEnvVariable("COMPRESSION_DB_PORT")
	user := ViperEnvVariable("COMPRESSION_DB_USER")
	password := ViperEnvVariable("COMPRESSION_DB_PASSWORD")
	dbname := ViperEnvVariable("COMPRESSION_DB_NAME")

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
