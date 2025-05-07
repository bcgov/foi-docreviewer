package utils

import (
	"database/sql"
	"fmt"
	"log"

	_ "github.com/lib/pq"
)

func GetDBConnection() *sql.DB {
	//cfg := LoadConfig()
	//fmt.Printf("\ncfg:%+v\n\n", cfg)

	//fmt.Printf("DedupeDBHost:%v\n", cfg.CompressionDBHost)

	host := ViperEnvVariable("DEDUPE_DB_HOST")         //cfg.CompressionDBHost         //os.Getenv("DEDUPE_DB_HOST")
	port := ViperEnvVariable("DEDUPE_DB_PORT")         //cfg.CompressionDBPort         //os.Getenv("DEDUPE_DB_PORT")
	user := ViperEnvVariable("DEDUPE_DB_USER")         //cfg.CompressionDBUser         //os.Getenv("DEDUPE_DB_USER")
	password := ViperEnvVariable("DEDUPE_DB_PASSWORD") //cfg.CompressionDBPassword //os.Getenv("DEDUPE_DB_PASSWORD")
	dbname := ViperEnvVariable("DEDUPE_DB_NAME")       //cfg.CompressionDBName       //os.Getenv("DEDUPE_DB_NAME")

	psqlInfo := fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		host, port, user, password, dbname,
	)
	fmt.Printf("psqlInfo:%v\n", psqlInfo)
	db, err := sql.Open("postgres", psqlInfo)
	if err != nil {
		log.Fatalf("Error connecting to DB: %v", err)
	}
	return db
}
