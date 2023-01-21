import tweepy
import statistics
import re
import pytz
import os
from logger import Logger
import logging

logging.basicConfig(level=logging.INFO)

class Tweet:
    def __init__(self, username, tweet, media):
        # Tweet ID
        self.id = tweet.id
        
        # Retweet Count
        self.rt_count = tweet.public_metrics["retweet_count"]

        # Like Count
        self.like_count = tweet.public_metrics["like_count"]

        # Reply Count
        self.reply_count = tweet.public_metrics["reply_count"]

        # Username
        self.username = username

        # Timestamp
        timestamp = tweet.created_at
        self.timestamp = (timestamp.astimezone(pytz.timezone('America/New_York'))) \
                        .strftime("%b %d %Y %I:%M:%S %p")

        # Link
        self.link = f"https://twitter.com/{self.username}/status/{tweet.id}";

        # Image
        self.media_url = media["url"] if (media != None) else None
        
        # Content
        content = tweet.text
        content = content.replace('\n', ' ')
        content = content.replace('"', '\\"')
        self.content = re.sub(r'http\S+', '', content)
        
class User:
    def __init__(self):
        self.tweets = []
        self.rt_counts = []
        self.like_counts = [] 
        self.reply_counts = []
        
    def add_tweet(self, tweet):
        self.tweets.append(tweet)
        self.rt_counts.append(tweet.rt_count)
        self.like_counts.append(tweet.like_count)
        self.reply_counts.append(tweet.reply_count)
        
    def sort_tweets(self):
        self.tweets = sorted(self.tweets, key=lambda t: t.like_count, reverse=True)
        
    def num_tweets(self):
        return len(self.tweets)

class TwitterScraper:
    __instance = None

    def __init__(self):
        if TwitterScraper.__instance != None:
            print("Tried to recreate instance")
        else:
            TwitterScraper.__instance = self
        
    def get_instance():
        if TwitterScraper.__instance is None:
            TwitterScraper()
        return TwitterScraper.__instance

    def authorize(self):
        Logger.get_instance().log("Beginning Twitter authorization")

        # Don't store keys
        bearer_token = os.environ['BEARER_TOKEN']

        # Authorize V2 tweepy client
        self.client = tweepy.Client(bearer_token=bearer_token)
        Logger.get_instance().log("Finished Twitter authorization")

    def get_user_tweets(self, username, count):
        Logger.get_instance().log(f"Attempting to scrape Twitter user @{username}'s {count} last tweets")
        user_tweets = []
        user_media = []
        
        try:
            # Get User ID
            user = self.client.get_user(username=username)
            user_id = user.data.id

            # Variables for the params to make it easier to tweak
            excludes = ["replies", "retweets"]
            expands = ["referenced_tweets.id", "attachments.media_keys"]
            medias =  ["public_metrics", "preview_image_url", "url"]
            tweet_fs = ["created_at", "public_metrics", "possibly_sensitive"]
            limit = (count // 100) + 1
            max_results = (count if (count <= 100) else 100)

            # Twitter v2 API only allows up to 100 messages per request
            # Use Paginator to aggregate all requests to get up to count tweets
            for response in tweepy.Paginator(self.client.get_users_tweets, user_id, 
                                             limit=limit,
                                             exclude=excludes,
                                             expansions=expands,
                                             media_fields=medias,
                                             tweet_fields=tweet_fs,
                                             max_results=max_results):
                tweets = response.data
                media = None
                if "media" in response.includes:
                    media = response.includes["media"]
                    user_media.extend(media)

                Logger.get_instance().log(f"Got {len(tweets)} from this response")
                user_tweets.extend(tweets)            
        except Exception as e:
            Logger.get_instance().log("Unknown exception occured")
            Logger.get_instance().log(f"Error: {e}")
            return None

        if len(user_tweets) > count:
            user_tweets = user_tweets[:count]
            
        Logger.get_instance().log(f"Retrieved {len(user_tweets)} from @{username}")
        return (user_tweets, user_media)
        
    def scrape_user(self, username, count):
        # Retrieve user's last tweets
        result = self.get_user_tweets(username, count)

        if result is None:
            return None

        user_tweets = result[0]
        user_media = result[1]
            
        if len(user_tweets) < 3:
            return None

        user = User()
        for tweet in user_tweets:
            media = None

            if (tweet.attachments != None) and ("media_keys" in tweet.attachments):
                media_key = tweet.attachments["media_keys"][0]
                media_item = [m for m in user_media if (media_key == m["media_key"])]
                if len(media_item) > 0:
                    media = media_item[0]
            
            this_tweet = Tweet(username, tweet, media)
            user.add_tweet(this_tweet)
            
        # Sort tweets by likes
        user.sort_tweets()

        return user

    def get_tweets_with_images(self, username, count):
        selected_tweets = []

        user = self.scrape_user(username, count)
        if user is None:
            return None
            
        for tweet in user.tweets:
            if tweet.media_url is None:
               continue

            selected_tweets.append(tweet)

        Logger.get_instance().log(f"Found {len(selected_tweets)} tweets with images")
        if len(selected_tweets) < 2:
            return None
        
        return selected_tweets
        
    def get_best_tweets(self, username, count):
        num_quantiles = 10
        quantile_threshold = 6

        user = self.scrape_user(username, count)
        if user is None:
            return None
            
        # Calculate different statistics about tweet's performance
        rt_mean = statistics.mean(user.rt_counts)
        like_mean = statistics.mean(user.like_counts)
        reply_mean = statistics.mean(user.reply_counts)
        
        rt_std_dev = statistics.stdev(user.rt_counts)
        like_std_dev = statistics.stdev(user.like_counts)
        reply_std_dev = statistics.stdev(user.reply_counts)
        
        rt_quant = statistics.quantiles(user.rt_counts, n=num_quantiles)[quantile_threshold]
        like_quant = statistics.quantiles(user.like_counts, n=num_quantiles)[quantile_threshold]
        reply_quant = statistics.quantiles(user.reply_counts, n=num_quantiles)[quantile_threshold]
        
        selected_tweets = []

        # Check if each tweet performed well
        for tweet in user.tweets:
            is_good = False
            
            is_good |= tweet.rt_count > (rt_mean + rt_std_dev) # Retweet Standard Deviation
            is_good |= tweet.like_count > (like_mean + like_std_dev) # Like Standard Deviation
            is_good |= tweet.reply_count > (reply_mean + reply_std_dev) # Reply Standard Devation
            
            is_good |= tweet.rt_count >= rt_quant # Retweet Quantile
            is_good |= tweet.like_count >= like_quant # Like Quantile
            is_good |= tweet.reply_count >= reply_quant # Reply Quantile

            if is_good:
                selected_tweets.append(tweet)

        Logger.get_instance().log(f"Found {len(selected_tweets)} that met criteria")
        return selected_tweets
