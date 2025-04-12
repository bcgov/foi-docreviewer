package utils

import (
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

// Struct for parsing the API response
type FormatResponse struct {
	Conversion    []string `json:"conversion"`
	Dedupe        []string `json:"dedupe"`
	NonRedactable []string `json:"nonredactable"`
}

// Config holds all configuration values
type Config struct {
	RedisHost            string
	RedisPort            string
	RedisPassword        string
	CompressionStreamKey string

	CompressionDBHost     string
	CompressionDBName     string
	CompressionDBPort     string
	CompressionDBUser     string
	CompressionDBPassword string

	CompressionS3Host    string
	CompressionS3Region  string
	CompressionS3Service string
	CompressionS3Env     string

	RequestManagementAPI string
	RecordFormatsPath    string

	PageCalculatorRedisHost     string
	PageCalculatorRedisPort     string
	PageCalculatorRedisPassword string
	PageCalculatorStreamKey     string
	HealthCheckInterval         int

	FileConversionTypes    []string
	CompressionFileTypes   []string
	NonRedactableFileTypes []string
}

// LoadConfig loads configuration from .env and environment variables
func LoadConfig() *Config {
	// Load .env file (ignore error if it doesn't exist, use env vars instead)
	_ = godotenv.Load()

	c := &Config{
		RedisHost:                   os.Getenv("REDIS_HOST"),
		RedisPort:                   os.Getenv("REDIS_PORT"),
		RedisPassword:               os.Getenv("REDIS_PASSWORD"),
		CompressionStreamKey:        os.Getenv("COMPRESSION_STREAM_KEY"),
		CompressionDBHost:           os.Getenv("COMPRESSION_DB_HOST"),
		CompressionDBName:           os.Getenv("COMPRESSION_DB_NAME"),
		CompressionDBPort:           os.Getenv("COMPRESSION_DB_PORT"),
		CompressionDBUser:           os.Getenv("COMPRESSION_DB_USER"),
		CompressionDBPassword:       os.Getenv("COMPRESSION_DB_PASSWORD"),
		CompressionS3Host:           os.Getenv("COMPRESSION_S3_HOST"),
		CompressionS3Region:         os.Getenv("COMPRESSION_S3_REGION"),
		CompressionS3Service:        os.Getenv("COMPRESSION_S3_SERVICE"),
		CompressionS3Env:            os.Getenv("COMPRESSION_S3_ENV"),
		RequestManagementAPI:        os.Getenv("COMPRESSION_REQUEST_MANAGEMENT_API"),
		RecordFormatsPath:           os.Getenv("COMPRESSION_RECORD_FORMATS"),
		PageCalculatorRedisHost:     os.Getenv("REDIS_HOST"),
		PageCalculatorRedisPort:     os.Getenv("REDIS_PORT"),
		PageCalculatorRedisPassword: os.Getenv("REDIS_PASSWORD"),
		PageCalculatorStreamKey:     os.Getenv("PAGECALCULATOR_STREAM_KEY"),
		HealthCheckInterval:         15, // default
	}

	// Try to parse interval if set
	if val := os.Getenv("HEALTH_CHECK_INTERVAL"); val != "" {
		if i, err := strconv.Atoi(val); err == nil {
			c.HealthCheckInterval = i
		}
	}

	//c.loadRecordFormats()

	return c
}

// Loads record formats from a remote JSON source
// func (c *Config) loadRecordFormats() {
// 	if c.RecordFormatsPath == "" {
// 		log.Println("No RecordFormatsPath provided.")
// 		c.setDefaultFileTypes()
// 		return
// 	}

// 	resp, err := http.Get(c.RecordFormatsPath)
// 	if err != nil {
// 		log.Println("Failed to fetch format config:", err)
// 		c.setDefaultFileTypes()
// 		return
// 	}
// 	defer resp.Body.Close()

// 	if resp.StatusCode != http.StatusOK {
// 		log.Printf("Bad status code from formats API: %d\n", resp.StatusCode)
// 		c.setDefaultFileTypes()
// 		return
// 	}

// 	body, err := io.ReadAll(resp.Body)
// 	if err != nil {
// 		log.Println("Error reading body:", err)
// 		c.setDefaultFileTypes()
// 		return
// 	}

// 	var formats FormatResponse
// 	if err := json.Unmarshal(body, &formats); err != nil {
// 		log.Println("Failed to unmarshal:", err)
// 		c.setDefaultFileTypes()
// 		return
// 	}

// 	c.FileConversionTypes = formats.Conversion
// 	c.DedupeFileTypes = formats.Dedupe
// 	c.NonRedactableFileTypes = formats.NonRedactable
// }

// Default types if S3 fails
// func (c *Config) setDefaultFileTypes() {
// 	c.FileConversionTypes = []string{".doc", ".docx", ".xls", ".xlsx", ".msg"}
// }
