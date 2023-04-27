from walrus import Database
from config import redishost,redisport,redispassword, notification_redishost, notification_redisport, notification_redispassword, health_check_interval


redisstreamdbwithparam =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword), retry_on_timeout=True, health_check_interval=int(health_check_interval), socket_keepalive=True)
notifcationstreamdbwithparam = Database(host=str(notification_redishost), port=str(notification_redisport), db=0,password=str(notification_redispassword), retry_on_timeout=True, health_check_interval=int(health_check_interval), socket_keepalive=True)

redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))
notifcationstreamdb = Database(host=str(notification_redishost), port=str(notification_redisport), db=0,password=str(notification_redispassword))