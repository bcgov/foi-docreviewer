from walrus import Database
from .foidocumentserviceconfig import redishost, redisport, redispassword


redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))