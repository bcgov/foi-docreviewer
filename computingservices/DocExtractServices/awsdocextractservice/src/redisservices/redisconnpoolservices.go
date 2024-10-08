package redisservices

import (
	"log"

	"github.com/gomodule/redigo/redis"
	"github.com/spf13/viper"
)

func GetFOIRedisConnectionPool() *redis.Pool {
	// Make a redis pool
	var redisPool = &redis.Pool{
		MaxActive: 5,
		MaxIdle:   5,
		Wait:      true,
		Dial: func() (redis.Conn, error) {
			//return redis.Dial("tcp", "localhost:6379")
			return redis.Dial("tcp", viperEnvVariable("redishostip")+":"+viperEnvVariable("redisport"), redis.DialPassword(viperEnvVariable("redispassword")))
		},
	}

	return redisPool
}

// use viper package to read .env file
// return the value of the key
func viperEnvVariable(key string) string {

	// SetConfigFile explicitly defines the path, name and extension of the config file.
	// Viper will use this and not check any of the config paths.
	// .env - It will search for the .env file in the current directory
	viper.SetConfigFile("./.env")

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
