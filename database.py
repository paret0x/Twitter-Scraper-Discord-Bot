import shelve

class Database:
    __instance = None
    __database_name = "twitter_users"
    __shelf = None
    __scrape_channel_key = "SCRAPE_CHANNEL"
    __selected_channel_key = "SELECT_CHANNEL"
    
    # Create Singleton instance of Database
    def __init__(self):
        if Database.__instance != None:
            print("Tried to recreate instance")
        else:
            Database.__instance = self
            Database.__instance.__shelf = shelve.open(Database.__database_name)
        
    def get_instance():
        if Database.__instance is None:
            Database()
        return Database.__instance
    
    def add_or_update_entry(self, username, entry):
        self.__shelf[username] = entry
        self.__shelf.sync()
        
    def get_entry(self, username):
        if username in self.__shelf:
            return self.__shelf[username]
        else:
            return None
    
    def remove_entry(self, username):
        if username in self.__shelf:
            del self.__shelf[username]
            self.__shelf.sync()

    def get_scrape_channel(self):
        return self.get_entry(self.__scrape_channel_key)

    def set_scrape_channel(self, channel):
        self.add_or_update_entry(self.__scrape_channel_key, channel)

    def get_select_channel(self):
        return self.get_entry(self.__selected_channel_key)

    def set_select_channel(self, channel):
        self.add_or_update_entry(self.__selected_channel_key, channel)
