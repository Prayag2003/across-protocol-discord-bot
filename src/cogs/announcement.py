# import os
# import re
# import asyncio
# import discord
# from loguru import logger
# from pymongo import MongoClient
# from discord.ext import commands
# from typing import List
# from dotenv import load_dotenv
# from services.mongo import MongoService

# load_dotenv()

# MONGO_URI = os.getenv("MONGO_URI")
# MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
# client = MongoClient(MONGO_URI)
# db = client[MONGO_DB_NAME]
# announcement_collection = db["announcements"]

# class AnnouncementChannelManager:
#     @staticmethod
#     async def get_announcement_channels(guild: discord.Guild) -> List[discord.TextChannel]:
#         """Find announcement-like channels in a guild."""
#         announcement_pattern = re.compile(r"announcement[s]?|update[s]?|new[s]?|chain-updates", re.IGNORECASE)
#         channels = [
#             channel for channel in guild.text_channels
#             if announcement_pattern.search(channel.name)
#         ]
#         # print(channels)
#         return channels

# class AnnouncementCog(commands.Cog):    
#     def __init__(self, bot: commands.Bot):
#         self.bot = bot
#         self.mongo_service = MongoService()
#         self.announcement_channels: List[discord.TextChannel] = []

#     async def update_announcement_channels(self, guild: discord.Guild):
#         """Update cached announcement channels for a given guild."""
#         logger.info(f"Announcement channels updated for {guild.name}: {self.announcement_channels}")
#         self.announcement_channels = await AnnouncementChannelManager.get_announcement_channels(guild)
    
#     @commands.Cog.listener()
#     async def on_ready(self):
#         """Populate announcement channels cache when the bot is ready."""
#         try:
#             logger.info("Bot is ready! Starting to populate announcement channels.")
#             await self.bot.wait_until_ready()

#             if not self.bot.guilds:
#                 logger.warning("The bot is not part of any guilds.")
#                 return

#             for guild in self.bot.guilds:
#                 logger.info(f"Processing guild: {guild.name} (ID: {guild.id})")
#                 await self.update_announcement_channels(guild)

#             logger.info("Announcement channels cache initialized. {}".format(self.announcement_channels))
#         except Exception as e:
#             logger.error(f"Error initializing announcement channels: {e}")

#     @commands.Cog.listener()
#     async def on_guild_channel_create(self, channel):
#         """Update cache if a new channel is created."""
#         if isinstance(channel, discord.TextChannel):
#             await self.update_announcement_channels(channel.guild)

#     @commands.Cog.listener()
#     async def on_message(self, message):

#         if message.author.bot:
#             return  

#         if message.content.startswith("/purge") or message.content.startswith("/purge confirm"):
#             return

#         # Check if the message is in an announcement channel
#         if message.channel.name in [channel.name for channel in self.announcement_channels]:
#             try:
#                 content = (
#                     message.content or
#                     " ".join(embed.description or embed.title or '' for embed in message.embeds) or
#                     " ".join(attachment.url for attachment in message.attachments)
#                 )
#                 if not content.strip():
#                     logger.info(f"No processable content in {message.channel.name} by {message.author.name}.")
#                     return

#                 logger.info(f"Processing message in {message.channel.name}: {content[:30] + '...' + content[-30:]}")

#                 metadata = {
#                     "content": content.strip(),
#                     "channel": message.channel.name,
#                     "author": message.author.name,
#                     "timestamp": message.created_at.isoformat(),
#                     "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
#                 }

#                 # logger.info(f"Metadata: {metadata}")

#                 # Save to MongoDB with Vector Search
#                 success = self.mongo_service.upsert_announcement(metadata)
#                 if success:
#                     logger.info(f"Announcement vectorized and stored in MongoDB Vector Search")
#                 else:
#                     logger.error("Failed to store announcement in MongoDB Vector Search.")

#             except Exception as e:
#                 logger.error(f"Failed to process announcement: {e}")

# async def setup(bot):
#     """Setup function to add the Explain Cog to the bot."""
#     await bot.add_cog(AnnouncementCog(bot))