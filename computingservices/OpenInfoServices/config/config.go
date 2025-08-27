package myconfig

import (
	"log"
	"os"
	"strconv"
	"sync"

	"github.com/spf13/viper"
)

var (
	//DB
	host     string
	port     string
	user     string
	password string
	dbname   string

	//Redis
	queue         string
	queuehost     string
	queueport     string
	queuepassword string

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

	//Keycloak
	keycloakurl          string
	keycloakrealm        string
	keycloakclientid     string
	keycloakclientsecret string
	keycloakuser         string
	keycloakpassword     string

	//Other
	env        string
	foiflowapi string
	mimetypes  string

	onceDB       sync.Once
	onceRedis    sync.Once
	onceS3       sync.Once
	onceS3Path   sync.Once
	onceKeycloak sync.Once
	onceOthers   sync.Once
)

// use viper package to read .env file
// return the value of the key
func viperEnvVariable(key string) string {

	// SetConfigFile explicitly defines the path, name and extension of the config file.
	// Viper will use this and not check any of the config paths.
	// .env - It will search for the .env file in given path
	viper.SetConfigFile(getEnv("ENVFILE_PATH"))

	// Find and read the config file
	err := viper.ReadInConfig()

	if err != nil {
		log.Fatalf("Error while reading config file %s", err)
	}

	// viper.Get() returns an empty interface{}
	// to get the underlying type of the key,
	// we have to do the type assertion, we know the underlying value is string
	// if we type assert to other type it will throw an error
	value, ok := viper.Get(key).(string)

	// If the type is a string then ok will be true
	// ok will make sure the program not break
	if !ok {
		log.Fatalf("Invalid type assertion")
	}

	return value
}

// Lazy initialization functions
func loadConfigDB() {
	host = getEnv("FOI_DB_HOST")
	port = getEnv("FOI_DB_PORT")
	user = getEnv("FOI_DB_USER")
	password = getEnv("FOI_DB_PASSWORD")
	dbname = getEnv("FOI_DB_NAME")
}

func loadConfigRedis() {
	queuehost = getEnv("OI_REDIS_HOST")
	queueport = getEnv("OI_REDIS_PORT")
	queuepassword = getEnv("OI_REDIS_PASSWORD")
}

func loadConfigS3() {
	region = getEnv("OI_S3_REGION")
	accessKey = getEnv("OI_ACCESS_KEY")
	secretKey = getEnv("OI_SECRET_KEY")
	s3host = getEnv("OI_S3_HOST")
}

func loadConfigS3Path() {
	s3url = "https://" + getEnv("OI_S3_HOST") + "/"
	oibucket = getEnv("OI_S3_BUCKET")
	oiprefix = getEnv("OI_PREFIX")
	sitemapprefix = getEnv("SITEMAP_PREFIX")

	var strerr error
	sitemaplimit, strerr = strconv.Atoi(getEnv("SITEMAP_PAGES_LIMIT"))
	if strerr != nil {
		log.Printf("Error converting string to int for SITEMAP_PAGES_LIMIT, will use default value: %v", strerr)
		sitemaplimit = 5000
	}
}

func loadConfigKeycloak() {
	keycloakurl = getEnv("KEYCLOAK_URL")
	keycloakrealm = getEnv("KEYCLOAK_URL_REALM")
	keycloakclientid = getEnv("KEYCLOAK_CLIENT_ID")
	keycloakclientsecret = getEnv("KEYCLOAK_CLIENT_SECRET")
	keycloakuser = getEnv("KEYCLOAK_USER")
	keycloakpassword = getEnv("KEYCLOAK_PASS")
}

func loadConfigOther() {
	env = getEnv("OI_S3_ENV")
	queue = getEnv("OI_QUEUE_NAME")
	foiflowapi = getEnv("FOIFLOW_BASE_API_URL")
	mimetypes = getEnv("OI_MIME_TYPEs")
}

// Helper function to get environment variables
func getEnv(key string) string {
	value, exists := os.LookupEnv(key)
	if !exists {
		return viperEnvVariable(key)
	}
	return value
}

// GetDB retrieves the database variables with lazy initialization
func GetDB() (string, string, string, string, string) {
	onceDB.Do(loadConfigDB) // Ensures loadConfig is called only once
	return host, port, user, password, dbname
}

// GetRedis retrieves the redis variables with lazy initialization
func GetRedis() (string, string, string) {
	onceRedis.Do(loadConfigRedis) // Ensures loadConfig is called only once
	return queuehost, queueport, queuepassword
}

// GetS3 retrieves the S3 variables with lazy initialization
func GetS3() (string, string, string, string) {
	onceS3.Do(loadConfigS3) // Ensures loadConfig is called only once
	return region, accessKey, secretKey, s3host
}

// GetS3 retrieves the S3 variables with lazy initialization
func GetS3Path() (string, string, string, string, int) {
	onceS3Path.Do(loadConfigS3Path) // Ensures loadConfig is called only once
	// For testing, destination bucket for opeinfo (oibucket) is always dev-openinfo
	if env != "" {
		oibucket = "dev" + "-" + oibucket
	}
	return s3url, oibucket, oiprefix, sitemapprefix, sitemaplimit
}

// GetKeycloak retrieves the Keycloak variables with lazy initialization
func GetKeycloak() (string, string, string, string, string, string) {
	onceKeycloak.Do(loadConfigKeycloak) // Ensures loadConfig is called only once
	return keycloakurl, keycloakrealm, keycloakclientid, keycloakclientsecret, keycloakuser, keycloakpassword
}

// GetS3 retrieves the S3 variables with lazy initialization
func GetOthers() (string, string, string, string) {
	onceOthers.Do(loadConfigOther) // Ensures loadConfig is called only once
	return env, queue, foiflowapi, mimetypes
}
