from walrus import Database
import os

from dotenv import load_dotenv
load_dotenv()

redishost = os.getenv('REDIS_HOST') 
redisport = os.getenv('REDIS_PORT')
redispassword = os.getenv('REDIS_PASSWORD')


redisstreamdb =  Database(host=str(redishost), port=str(redisport), db=0,password=str(redispassword))