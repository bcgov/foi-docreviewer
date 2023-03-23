from walrus import Database
from config import redishost,redisport,redispassword


redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))