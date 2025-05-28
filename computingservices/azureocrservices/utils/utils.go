package utils

import (
	"log"

	"github.com/joho/godotenv"
	"github.com/spf13/viper"
)

// use viper package to read .env file
// return the value of the key
func ViperEnvVariable(key string) string {
	err := godotenv.Load(".env")
	if err != nil {
		log.Printf("Error loading .env file: %v", err)
	}

	// Tell viper to automatically get from environment variables
	viper.AutomaticEnv()
	//viper.AutomaticEnv()
	// viper.Get() returns an empty interface{}
	// to get the underlying type of the key,
	// we have to do the type assertion, we know the underlying value is string
	// if we type assert to other type it will throw an error
	//value, ok := viper.Get(key).(string)
	value := viper.GetString(key)
	if value == "" {
		log.Printf("Key %s not found in environment variables", key)
	}
	return value
}
