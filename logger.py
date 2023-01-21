import time

class Logger:
    __instance = None
    __file_name = "logs.txt"

    def __init__(self):
        if Logger.__instance != None:
            print("Tried to recreate instance")
        else:
            Logger.__instance = self
        
    def get_instance():
        if Logger.__instance is None:
            Logger()
        return Logger.__instance

    def log(self, msg):
        log_file = open(self.__file_name, "a")
        timestamp = time.localtime()
        current_time = time.strftime("[%d/%m/%Y %H:%M:%S]", timestamp)
        new_msg = current_time + " " + msg + "\n"
        log_file.write(new_msg)
        log_file.close()
