package redisservices

import (
	"github.com/gomodule/redigo/redis"
)

func GetFOIRedisConnectionPool() *redis.Pool {
	// Make a redis pool
	var redisPool = &redis.Pool{
		MaxActive: 5,
		MaxIdle:   5,
		Wait:      true,
		Dial: func() (redis.Conn, error) {
			return redis.Dial("tcp", "localhost:6379")
		},
	}

	return redisPool
}
