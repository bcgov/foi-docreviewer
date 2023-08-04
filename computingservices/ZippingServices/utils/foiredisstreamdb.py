from walrus import Database
from .foizipperconfig import redishost,redisport,redispassword, notification_redis_host,notification_redis_port,notification_redis_password


redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))

notificationredisstreamdb =  Database(host=str(notification_redis_host), port=str(notification_redis_port), db=0,password=str(notification_redis_password))
