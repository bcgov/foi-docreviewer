from threading import Thread
import eventlet
#Monkey patch to allow for async actions (aka multiple workers)
eventlet.monkey_patch()
from distutils.log import debug


import os
from reviewer_api import create_app

APP = create_app()
if __name__ == "__main__":
    APP.run(host="0.0.0.0", debug=True)
