package envtool

import (
	"log"
	"os"

	"github.com/spf13/viper"
)

func SetEnvFromFile() {
	viper.SetConfigFile(".env")

	// Find and read the config file
	err := viper.ReadInConfig()

	if err != nil {
		log.Fatalf("Error while reading config file %s", err)
	}
}

// GetEnv retrieves the value of the environment variable named by the key.
// It returns the value, or the defaultValue if the variable is not present.
func GetEnv(key, defaultValue string) string {
	value, exists := os.LookupEnv(key)
	if !exists {
		return defaultValue
	}
	return value
}
