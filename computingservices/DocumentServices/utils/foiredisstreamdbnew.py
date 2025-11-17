import redis
from .foidocumentserviceconfig import redishost, redisport, redispassword

redisstreamdbnew =  redis.Redis(host=str(redishost), port=str(redisport), db=0, password=str(redispassword))