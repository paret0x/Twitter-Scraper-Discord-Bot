from flask import Flask
from threading import Thread
from logger import Logger

web = Flask('keep_alive')

@web.route('/')
def home():
    return "I am alive!"

def run():
    Logger.get_instance().log("Starting flask server")
    web.run(host='0.0.0.0',port=8080)
    Logger.get_instance().log("Finished starting flask server")

def keep_alive():
    Logger.get_instance().log("Starting Flask thread")
    run_thread = Thread(target=run)
    run_thread.start()
