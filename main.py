import os
import keep_alive
import time
import discord
from twitter import TwitterScraper
from logger import Logger
from discord import app_commands
from discord_client import DiscordClient
from database import Database

intents = discord.Intents.default()
intents.message_content = True
client = DiscordClient(intents=intents)
is_busy = False
is_stopped = False

# On bot connecting to server
@client.event
async def on_ready():
    Logger.get_instance().log(f"@{client.user} connected to Discord")
    await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="twitch.tv/stormy"))


# On bot disconnecting from server
@client.event
async def on_disconnect():
    Logger.get_instance().log(f"@{client.user} disconnected from Discord")

# Catch event for a reaction being added to a message
@client.event
async def on_raw_reaction_add(payload):
    if payload.event_type != "REACTION_ADD":
        return

    # Reaction was not from bot
    if payload.user_id == client.user.id:
        return

    # Get more info about the original message
    message = await client.get_channel(payload.channel_id).fetch_message(payload.message_id)

    # Original message not sent by bot
    if message.author != client.user:
        return

    # Shouldn't happen, but just in case message doesn't have embed
    if len(message.embeds) == 0:
        Logger.get_instance().log("Original message had no embeds?")
        return

    # Grab the embed from the original message
    embed_msg = message.embeds[0]
    channel = client.get_channel(Database.get_instance().get_select_channel())

    Logger.get_instance().log(f"Sending embed to channel {channel.id}")

    # Send new message in Selected channel with embed
    await channel.send(embed=embed_msg)

# To not overload Discord API rate limiter, send messages with a delay inbetween
async def loop_through_messages(tweets):
    global is_stopped
    
    sleep_time = 3 # seconds
    Logger.get_instance().log(f"Iterating through {len(tweets)} tweets")
    for i in range(len(tweets)):
        if is_stopped:
            Logger.get_instance().log("Was stopped")
            return
        
        tweet = tweets[i]
        count = i + 1
        remaining = len(tweets) - count

        try:
            embed_msg = discord.Embed(title=f'Tweet from {tweet.username} at {tweet.timestamp}',
                                      url=tweet.link,
                                      color=0xe67e22,
                                      description=tweet.content)
            if tweet.media_url != None:
                embed_msg.set_image(url=tweet.media_url)
                embed_msg.image.url = tweet.media_url
    
            embed_msg.set_footer(text=f"Users gave this tweet {tweet.rt_count} retweets, "
                                      f"{tweet.like_count} likes, and {tweet.reply_count} replies. "
                                      f"(Tweet {count}/{len(tweets)})")
            channel = client.get_channel(Database.get_instance().get_scrape_channel())
            Logger.get_instance().log(f"Attempting to send embed for tweet {tweet.id}. "
                                      f"{remaining} tweets left")
            message = await channel.send(embed=embed_msg)
            await message.add_reaction('👍')
        except Exception as e:
            Logger.get_instance().log(f"Encountered error while sending embed. Error: {e}")
        
        time.sleep(sleep_time)

# Command to set channel to scrape tweets from
@client.tree.command(description='Change active channel for bot scrape')
@app_commands.checks.has_permissions(administrator=True)
async def scrape_channel(interaction: discord.Interaction):
    Database.get_instance().set_scrape_channel(interaction.channel_id)
    await interaction.response.send_message(f'Set intended scrape channel to {interaction.channel.name}')

# Command to set channel to send "selected" tweets to
@client.tree.command(description='Change active channel for bot selection')
@app_commands.checks.has_permissions(administrator=True)
async def select_channel(interaction: discord.Interaction):
    Database.get_instance().set_select_channel(interaction.channel_id)
    await interaction.response.send_message(f'Set intended select channel to {interaction.channel.name}')

# Determine if bot should handle a scrape command
async def should_continue(interaction: discord.Interaction):
    global is_busy

    # If busy processing other command, don't process new one
    if is_busy:
        Logger.get_instance().log("Still busy working on last command.")
        await interaction.edit_original_response(content="Still busy working on last command.")
        return False

    channel = Database.get_instance().get_scrape_channel()

    # If scrape channel hasn't been set, don't process it
    if channel is None:
        Logger.get_instance().log("Command used before /scrape_channel used")
        await interaction.edit_original_response(content="Set the channel first")
        return False

    # If command sent from not the scrape channel, don't process it
    if channel != interaction.channel_id:
        Logger.get_instance().log("Was not from scrape channel")
        await interaction.edit_original_response(content="Wrong channel!")
        return False

    return True

# Command to scrape "best" tweets from user
@client.tree.command(description='Scrape the best tweets of a given user')
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    username='The Twitter handle of the user to scrape',
    count='The amount of tweets to attempt to scrape'
)
async def scrape_best(interaction: discord.Interaction, username: str, count: int):
    global is_busy, is_stopped
    Logger.get_instance().log(f"Asked to scrape @{username}'s {count} last tweets")
    await interaction.response.send_message(f"Attempting to scrape the best of @{username}'s {count} last tweets")

    result = await should_continue(interaction)
    if not result:
        return
    
    is_busy = True
    is_stopped = False
    tweets = TwitterScraper.get_instance().get_best_tweets(username, count)
    if tweets is None:
        await interaction.edit_original_response(content="Didn't find enough tweets")
        is_busy = False
        return
    
    await interaction.edit_original_response(content=f'Found {len(tweets)} tweets from {username}.')
    await loop_through_messages(tweets=tweets)
    is_busy = False

# Command to scrape all tweets with images from user
@client.tree.command(description='Scrape the tweets with images of a given user')
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(
    username='The Twitter handle of the user to scrape',
    count='The amount of tweets to attempt to scrape'
)
async def scrape_images(interaction: discord.Interaction, username: str, count: int):
    global is_busy, is_stopped
    Logger.get_instance().log(f"Asked to scrape @{username}'s {count} last tweets with images")
    await interaction.response.send_message(f"Attempting to scrape @{username}'s {count} last tweets with images")
    
    result = await should_continue(interaction)
    if not result:
        return
    
    is_busy = True
    is_stopped = False
    tweets = TwitterScraper.get_instance().get_tweets_with_images(username, count)
    if tweets is None:
        await interaction.edit_original_response(content="Didn't find enough tweets")
        is_busy = False
        return
    
    await interaction.edit_original_response(content=f'Found {len(tweets)} tweets with images from {username}')
    await loop_through_messages(tweets=tweets)
    is_busy = False

@client.tree.command(description='Stop the output of the ongoing responses')
@app_commands.checks.has_permissions(administrator=True)
async def stop_scrape(interaction: discord.Interaction):
    global is_busy, is_stopped
    Logger.get_instance().log("Asked to stop ongoing command")

    if not is_busy:
        Logger.get_instance().log("Wasn't busy")
        await interaction.response.send_message("Not currently scraping, nothing to stop")
        return

    is_stopped = True
    Logger.get_instance().log("Stopped successfully")
    await interaction.response.send_message("Stopped previous command")


@client.tree.command(description="test command")
@app_commands.checks.has_permissions(administrator=True)
async def test_client(interaction: discord.Interaction):
    print("Testing client")
    TwitterScraper.get_instance().test_client()

# Main function
if __name__ == "__main__":
    Logger.get_instance().log("Starting program")
    
    is_busy = False
    TwitterScraper.get_instance().authorize()

    try:
        keep_alive.keep_alive()
        TOKEN = os.environ['DISCORD_TOKEN']
        client.run(TOKEN)
    except discord.errors.HTTPException as e:
        Logger.get_instance().log(f"Exception occured. HTTP Status: {e.status}. Discord Code: {e.code}")
        os.system('kill 1')
    except Exception as e:
        Logger.get_instance().log("Unknown exception occured")
        Logger.get_instance().log(f"Error: {e}")
        os.system('kill 1')
    finally:
        Logger.get_instance().log("Program wrapping up execution")
    