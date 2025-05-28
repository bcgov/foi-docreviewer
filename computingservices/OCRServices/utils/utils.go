package utils

import (
	"github.com/spf13/viper"
)

func ViperEnvVariable(key string) string {
	// SetConfigFile explicitly defines the path, name and extension of the config file.
	// Viper will use this and not check any of the config paths.
	// .env - It will search for the .env file in the current directory
	// viper.SetConfigName(".env")
	// viper.SetConfigType("env")
	// viper.AddConfigPath(".")

	// // Find and read the config file
	// err := viper.ReadInConfig()
	// if err != nil {
	// 	log.Fatalf("Error while reading config file %s", err)
	// }
	viper.AutomaticEnv()
	// viper.Get() returns an empty interface{}
	// to get the underlying type of the key,
	// we have to do the type assertion, we know the underlying value is string
	// if we type assert to other type it will throw an error
	value := viper.GetString(key)
	// If the type is a string then ok will be true
	// ok will make sure the program not break
	// if !ok {
	// 	log.Fatalf("Invalid type assertion")
	// }
	return value
}

func ViperEnvVariableWithDefault(key string, defaultVal string) string {
	// viper.SetConfigName(".env")
	// viper.SetConfigType("env")
	// viper.AddConfigPath(".")
	// err := viper.ReadInConfig()
	// if err != nil {
	// 	log.Printf("Warning: Error while reading config file: %s. Using default for %s", err, key)
	// 	return defaultVal
	// }
	viper.AutomaticEnv()
	value := viper.GetString(key)
	// if !ok || value == "" {
	// 	log.Printf("Warning: Config key '%s' not found or invalid. Using default: %s", key, defaultVal)
	// 	return defaultVal
	// }
	return value
}
