import os
import re
import asyncio
import discord
from discord.ext import commands
from loguru import logger 
from typing import List, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from utils.message import chunk_message_by_paragraphs
from utils.logging import log_manager
from inference.inference import generate_response_with_context
from services.pinecone import PineconeService
load_dotenv()

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
    async def send_explanation_in_thread(message: discord.Message, explanation: str) -> Optional[discord.Thread]:
        """Send explanation in a thread attached to the original message."""
        try:
            thread = await message.create_thread(
                name=message.content[:80] + "...",
                auto_archive_duration=60
            )
            explanation_chunks = chunk_message_by_paragraphs(explanation)
            for chunk in explanation_chunks:
                await thread.send(chunk.strip())
            return thread
        except discord.errors.HTTPException as e:
            logger.error(f"Thread creation error: {e}")
            return None

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcement_channels: List[discord.TextChannel] = []
        self.pinecone_service = PineconeService(
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            openai_api_key=os.getenv("OPENAI_API_KEY")
        )

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
        logger.debug(f"Received message in channel: {message.channel.name}")
        """Process new announcements and add them to MongoDB."""
        if message.author.bot:
            return

        if message.channel.name in [channel.name for channel in self.announcement_channels]:
            try:
                content = (
                    message.content or 
                    " ".join(embed.description or embed.title or '' for embed in message.embeds) or 
                    " ".join(attachment.url for attachment in message.attachments)
                )

                if not content.strip():
                    logger.info(f"No processable content in {message.channel.name} by {message.author.name}.")
                    return

                # Debug log to confirm processing
                logger.info(f"Processing message in {message.channel.name}: {content}")

                metadata = {
                    "content": content.strip(),
                    "channel": message.channel.name,
                    "author": message.author.name,
                    "timestamp": message.created_at.isoformat(),
                    "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                }

                logger.info(f"Metadata: {metadata}")

                # Save to Pinecone (implement upsert_announcement if not done)
                success = self.pinecone_service.upsert_announcement(metadata)
                if success:
                    logger.info(f"Announcement vectorized and stored in Pinecone. Channel: {message.channel.name}")
                else:
                    logger.error("Failed to store announcement in Pinecone.")

                # Save to MongoDB
                announcement_collection.insert_one(metadata)
                logger.info(f"Announcement stored in MongoDB. Channel: {message.channel.name}, Author: {message.author.name}")

            except Exception as e:
                logger.error(f"Failed to process announcement: {e}")

    @commands.command(name='event')
    async def event(self, ctx, *, user_query: str):
        """Handle user query and generate response from Pinecone."""
        try:
            response = self.pinecone_service.generate_response_from_pinecone(user_query)
            await log_manager.stream_log(ctx.message, response=response)

            if response.get("response"):
                await ctx.channel.send(response["response"])
            else:
                await ctx.channel.send("No response generated from Pinecone.")
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await ctx.channel.send(f"An error occurred: {e}")

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        try:
            username = ctx.author.name
            explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
            explanation = explanation.strip()
            logger.info(f"Full explanation length: {len(explanation)}")
            await log_manager.stream_log(ctx.message, explanation)

            if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
                await DiscordResponseHandler.send_explanation_in_thread(ctx.message, explanation)
            else:
                error_msg = "Threads are not supported in this channel. Please use this command in a text channel."
                await ctx.channel.send(error_msg)
                logger.warning(error_msg)
        except discord.errors.HTTPException as http_ex:
            logger.error(f"Error sending the explanation: {str(http_ex)}")
            await ctx.channel.send(f"Error: {http_ex}")
        except Exception as e:
            logger.error(f"Error: {e}")
            await ctx.channel.send(f"An error occurred: {e}")


async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))
