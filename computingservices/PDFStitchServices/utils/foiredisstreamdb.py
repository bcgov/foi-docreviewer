from walrus import Database
from config import redishost,redisport,redispassword, notification_redishost, notification_redisport, notification_redispassword


redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))
notifcationstreamdb = Database(host=str(notification_redishost), port=str(notification_redisport), db=0,password=str(notification_redispassword))