import discord
import os
from logger import Logger
from discord import app_commands

class DiscordClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        Logger.get_instance().log("Setting up Discord hook")
        guild = discord.Object(id=os.environ['GUILD'])
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        Logger.get_instance().log("Finished setting up Discord hook")