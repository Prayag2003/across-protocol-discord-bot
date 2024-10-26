from discord.ext import commands
from permissions.intents import intents

def create_bot():
    """Create and configure the bot instance"""
    bot = commands.Bot(command_prefix="!", intents=intents)
    return bot