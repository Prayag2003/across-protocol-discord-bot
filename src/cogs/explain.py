# import discord
# from discord.ext import commands
# from loguru import logger as logging
# import asyncio
# from utils.message import chunk_message_by_paragraphs
# from utils.logging import log_manager
# from inference.inference import generate_response_with_context
# class ExplainCog(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     @commands.command(name='explain')
#     async def explain(self, ctx, *, user_query: str):
#         try:
#             username = ctx.author.name
#             explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
#             explanation = explanation.strip()
#             logging.info(f"Full explanation length: {len(explanation)}")

#             await log_manager.stream_log(ctx.message, explanation)

#             if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
#                 thread = await ctx.message.create_thread(
#                     name=f"{user_query[:80]}...",
#                     auto_archive_duration=60
#                 )

#                 explanation_chunks = chunk_message_by_paragraphs(explanation)
#                 for chunk in explanation_chunks:
#                     chunk = chunk.strip()
#                     logging.info(f"Chunk length: {len(chunk)}")
#                     await thread.send(chunk)
                    
#             else:
#                 error_msg = "Threads are not supported in this channel. Please use this command in a text channel."
#                 await ctx.channel.send(error_msg)
#                 logging.warning(error_msg)

#         except discord.errors.HTTPException as http_ex:
#             error_msg = f"Error sending the explanation: {str(http_ex)}"
#             logging.error(error_msg)
#             await ctx.channel.send(error_msg)
#             await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

#         except Exception as e:
#             error_msg = f"An error occurred: {str(e)}"
#             logging.error(error_msg)
#             await ctx.channel.send(error_msg)
#             await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

# async def setup(bot):
#     await bot.add_cog(ExplainCog(bot))









# import discord
# from discord.ext import commands
# import asyncio
# import re
# from typing import List, Optional
# from loguru import logger
# from utils.message import chunk_message_by_paragraphs
# from utils.logging import log_manager
# from pymongo import MongoClient
# import os

# # Load environment variables
# from dotenv import load_dotenv
# load_dotenv()

# # MongoDB setup
# MONGO_URI = os.getenv("MONGO_URI")
# MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
# client = MongoClient(MONGO_URI)
# db = client[MONGO_DB_NAME]
# announcement_collection = db["announcements"]

# class AnnouncementChannelManager:
#     @staticmethod
#     async def get_announcement_channels(guild: discord.Guild) -> List[discord.TextChannel]:
#         """Find announcement-like channels in a guild."""
#         announcement_pattern = re.compile(r"announcement[s]?", re.IGNORECASE)
#         return [
#             channel for channel in guild.text_channels
#             if announcement_pattern.search(channel.name)
#         ]

# class DiscordResponseHandler:
#     @staticmethod
#     async def send_explanation_in_thread(
#         message: discord.Message, 
#         explanation: str
#     ) -> Optional[discord.Thread]:
#         """Send explanation in a thread attached to the original message."""
#         try:
#             thread = await message.create_thread(
#                 name=message.content[:80] + "...",
#                 auto_archive_duration=60
#             )

#             explanation_chunks = chunk_message_by_paragraphs(explanation)
#             for chunk in explanation_chunks:
#                 chunk = chunk.strip()
#                 await thread.send(chunk)
            
#             return thread
#         except discord.errors.HTTPException as e:
#             logger.error(f"Thread creation error: {e}")
#             return None

# class ExplainCog(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot
#         self.announcement_channels: List[discord.TextChannel] = []

#     async def update_announcement_channels(self, guild: discord.Guild):
#         """Update cached announcement channels for a given guild."""
#         self.announcement_channels = await AnnouncementChannelManager.get_announcement_channels(guild)
#         logger.info(f"Updated announcement channels: {[c.name for c in self.announcement_channels]}")

#     @commands.Cog.listener()
#     async def on_ready(self):
#         """Populate announcement channels cache when the bot is ready."""
#         for guild in self.bot.guilds:
#             await self.update_announcement_channels(guild)
#         logger.info("Announcement channels cache initialized.")

#     @commands.Cog.listener()
#     async def on_guild_channel_create(self, channel):
#         """Update cache if a new channel is created."""
#         if isinstance(channel, discord.TextChannel):
#             await self.update_announcement_channels(channel.guild)

#     @commands.Cog.listener()
#     async def on_message(self, message):
#         """Process new announcements and add them to MongoDB."""
#         if message.author.bot:
#             return

#         if message.channel in self.announcement_channels:
#             try:
#                 content = message.content
#                 if not content:
#                     logger.info(f"Empty message in {message.channel.name} by {message.author.name}, ignoring.")
#                     return

#                 # Fallback: Extract embeds or attachment URLs if content is empty
#                 if not content:
#                     if message.embeds:
#                         content = " ".join(embed.description or embed.title or '' for embed in message.embeds)
#                     elif message.attachments:
#                         content = " ".join(attachment.url for attachment in message.attachments)

#                 # Final check if content is still empty
#                 if not content:
#                     logger.info(f"No processable content in {message.channel.name} by {message.author.name}.")
#                     return

#                 # Store announcement in MongoDB
#                 metadata = {
#                     "content": content,
#                     "channel": message.channel.name,
#                     "author": message.author.name,
#                     "timestamp": message.created_at.isoformat(),
#                     "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
#                 }
#                 announcement_collection.insert_one(metadata)
#                 logger.info(f"Announcement successfully stored in MongoDB! Channel: {message.channel.name}, Author: {message.author.name}")

#             except Exception as e:
#                 error_msg = f"Failed to process announcement in {message.channel.name} by {message.author.name}: {e}"
#                 logger.error(error_msg)
#                 await log_manager.stream_log(message, f"ERROR: {error_msg}")

#     @commands.command(name='explain')
#     async def explain(self, ctx, *, user_query: str):
#         """Generate an explanation for the user query."""
#         try:
#             # Generate explanation in a separate thread
#             explanation = await asyncio.to_thread(
#                 self.generate_response_with_context, 
#                 user_query, 
#                 ctx.author.name
#             )
#             logger.info(f"Full explanation length: {len(explanation)}")

#             # Log the explanation
#             await log_manager.stream_log(ctx.message, explanation)

#             # Check if the channel supports threads
#             if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
#                 # Use response handler to create thread and send explanation
#                 await DiscordResponseHandler.send_explanation_in_thread(
#                     ctx.message, 
#                     explanation
#                 )
#             else:
#                 error_msg = "Threads are not supported in this channel. Please use this command in a text channel."
#                 await ctx.channel.send(error_msg)
#                 logger.warning(error_msg)

#         except discord.errors.HTTPException as http_ex:
#             error_msg = f"Error sending the explanation: {str(http_ex)}"
#             logger.error(error_msg)
#             await ctx.channel.send(error_msg)
#             await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

#         except Exception as e:
#             error_msg = f"An error occurred: {str(e)}"
#             logger.error(error_msg)
#             await ctx.channel.send(error_msg)
#             await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

#     def generate_response_with_context(self, query, username):
#         """Placeholder for explanation generation logic."""
#         return f"Generated explanation for {query} by {username}"

# async def setup(bot):
#     """Setup function to add the Explain Cog to the bot."""
#     await bot.add_cog(ExplainCog(bot))





import os
import sys
import re
import asyncio
import discord
from discord.ext import commands
from typing import List, Optional
from loguru import logger
from pymongo import MongoClient
from dotenv import load_dotenv
from utils.message import chunk_message_by_paragraphs
from utils.logging import log_manager

# Add the 'knowledge_base' folder to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'knowledge_base'))

# Import modules from the knowledge_base folder
import generate_embeddings
import generate_embeddings_announcement
from knowledge_base.generate_embeddings_announcement import generate_embeddings_for_announcements

# Load environment variables
load_dotenv()

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
announcement_collection = db["announcements"]

class AnnouncementChannelManager:
    @staticmethod
    async def get_announcement_channels(guild: discord.Guild) -> List[discord.TextChannel]:
        """Find announcement-like channels in a guild."""
        announcement_pattern = re.compile(r"announcement[s]?", re.IGNORECASE)
        return [
            channel for channel in guild.text_channels
            if announcement_pattern.search(channel.name)
        ]

class DiscordResponseHandler:
    @staticmethod
    async def send_explanation_in_thread(
        message: discord.Message, 
        explanation: str
    ) -> Optional[discord.Thread]:
        """Send explanation in a thread attached to the original message."""
        try:
            thread = await message.create_thread(
                name=message.content[:80] + "...",
                auto_archive_duration=60
            )

            explanation_chunks = chunk_message_by_paragraphs(explanation)
            for chunk in explanation_chunks:
                chunk = chunk.strip()
                await thread.send(chunk)
            
            return thread
        except discord.errors.HTTPException as e:
            logger.error(f"Thread creation error: {e}")
            return None

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcement_channels: List[discord.TextChannel] = []

    async def update_announcement_channels(self, guild: discord.Guild):
        """Update cached announcement channels for a given guild."""
        self.announcement_channels = await AnnouncementChannelManager.get_announcement_channels(guild)
        logger.info(f"Updated announcement channels: {[c.name for c in self.announcement_channels]}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Populate announcement channels cache when the bot is ready."""
        for guild in self.bot.guilds:
            await self.update_announcement_channels(guild)
        logger.info("Announcement channels cache initialized.")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        """Update cache if a new channel is created."""
        if isinstance(channel, discord.TextChannel):
            await self.update_announcement_channels(channel.guild)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Process new announcements and add them to MongoDB."""
        if message.author.bot:
            return

        if message.channel in self.announcement_channels:
            try:
                content = message.content
                if not content:
                    logger.info(f"Empty message in {message.channel.name} by {message.author.name}, ignoring.")
                    return

                # Fallback: Extract embeds or attachment URLs if content is empty
                if not content:
                    if message.embeds:
                        content = " ".join(embed.description or embed.title or '' for embed in message.embeds)
                    elif message.attachments:
                        content = " ".join(attachment.url for attachment in message.attachments)

                # Final check if content is still empty
                if not content:
                    logger.info(f"No processable content in {message.channel.name} by {message.author.name}.")
                    return

                # Store announcement in MongoDB
                metadata = {
                    "content": content,
                    "channel": message.channel.name,
                    "author": message.author.name,
                    "timestamp": message.created_at.isoformat(),
                    "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                }
                announcement_collection.insert_one(metadata)
                logger.info(f"Announcement successfully stored in MongoDB! Channel: {message.channel.name}, Author: {message.author.name}")

                # Call the embedding generation functions after storing the announcement
                logger.info("Calling generate_embeddings_announcement for announcements with embeddings.")
                await asyncio.to_thread(generate_embeddings_announcement.generate_embeddings_announcement, [metadata])
                logger.info("Called generate_embeddings_announcement for embeddings.")

            except Exception as e:
                error_msg = f"Failed to process announcement in {message.channel.name} by {message.author.name}: {e}"
                logger.error(error_msg)
                await log_manager.stream_log(message, f"ERROR: {error_msg}")

    @commands.command(name="generate_embeddings")
    async def generate_embeddings_command(self, ctx):
        """Command to generate embeddings for the knowledge base."""
        try:
            knowledge_base_path = os.path.join("knowledge_base", "knowledge_base.json")
            output_path = os.path.join("knowledge_base", "embeddings.json")
            
            logger.info("Loading knowledge base...")
            knowledge_base = generate_embeddings.load_knowledge_base(knowledge_base_path)

            logger.info("Generating embeddings...")
            embeddings = generate_embeddings.create_embeddings_for_kb(knowledge_base)

            logger.info("Saving embeddings...")
            generate_embeddings.save_embeddings(embeddings, output_path)

            await ctx.send("Embeddings generated and saved successfully.")
            logger.info("Embeddings generation completed.")

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            await ctx.send("Failed to generate embeddings.")

    @commands.command(name="generate_announcement_embeddings")
    async def generate_announcement_embeddings_command(self, ctx):
        """Command to generate embeddings for announcements."""
        try:
            logger.info("Loading announcements...")
            announcements = generate_embeddings_announcement.load_announcements()

            logger.info("Generating embeddings for announcements...")
            output_path = os.path.join("knowledge_base", "announcements", "embeddings_announcements.json")
            generate_embeddings_announcement.generate_embeddings_announcement(announcements)

            await ctx.send("Announcement embeddings generated and saved successfully.")
            logger.info("Announcement embeddings generation completed.")

        except Exception as e:
            logger.error(f"Error generating announcement embeddings: {e}")
            await ctx.send("Failed to generate announcement embeddings.")

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        try:
            # Generate explanation in a separate thread
            explanation = await asyncio.to_thread(
                self.generate_response_with_context, 
                user_query, 
                ctx.author.name
            )
            logger.info(f"Full explanation length: {len(explanation)}")

            # Log the explanation
            await log_manager.stream_log(ctx.message, explanation)

            # Check if the channel supports threads
            if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
                # Use response handler to create thread and send explanation
                await DiscordResponseHandler.send_explanation_in_thread(
                    ctx.message, 
                    explanation
                )
            else:
                error_msg = "Threads are not supported in this channel. Please use this command in a text channel."
                await ctx.channel.send(error_msg)
                logger.warning(error_msg)

        except discord.errors.HTTPException as http_ex:
            error_msg = f"Error sending the explanation: {str(http_ex)}"
            logger.error(error_msg)
            await ctx.channel.send(error_msg)
            await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            await ctx.channel.send(error_msg)
            await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

    def generate_response_with_context(self, query, username):
        """Placeholder for explanation generation logic."""
        return f"Generated explanation for {query} by {username}"

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))
