import os
import re
import io
import asyncio
import discord
from discord.ext import commands
from loguru import logger
from typing import List, Optional, Dict
from dotenv import load_dotenv
from pymongo import MongoClient
from utils.message import chunk_message_by_paragraphs, extract_code_blocks, get_file_extension
from inference.inference import generate_response_with_context
from services.mongo import MongoService
from utils.logging import log_manager
import sys
import json
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
        announcement_pattern = re.compile(r"announcement[s]?|update[s]?", re.IGNORECASE)
        return [
            channel for channel in guild.text_channels
            if announcement_pattern.search(channel.name)
        ]

class DiscordResponseHandler:
    @staticmethod
    async def send_explanation_in_thread(message: discord.Message, explanation: str) -> Optional[discord.Thread]:
        try:
            thread_name = thread_name = (message.content[:50] + "...") if len(message.content) > 50 else message.content
            thread = await message.create_thread(
                name = thread_name,
                auto_archive_duration=60
            )

            # segregate the code blocks and text content
            clean_text, code_blocks = extract_code_blocks(explanation)

            for idx, code_block in enumerate(code_blocks, 1):
                language = code_block["language"]
                extension = get_file_extension(language)
                
                # Check if the code is small (less than 500 characters) or large
                if len(code_block["code"]) <= 500:
                    # Small code, send it in the message directly with syntax highlighting
                    await thread.send(f"```{language}\n{code_block['code']}```")
                else:
                    # Large code, send it as a file
                    file = discord.File(
                        io.StringIO(code_block["code"]),
                        filename=f"code_snippet_{idx}.{extension}"
                    )
                    await thread.send(file=file)

            if clean_text:
                text_chunks = chunk_message_by_paragraphs(clean_text)
                for chunk in text_chunks:
                    if chunk.strip():
                        await thread.send(chunk.strip())
            return thread

        except discord.errors.HTTPException as e:
            logger.error(f"Thread creation error: {e}")
            return None

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.announcement_channels: List[discord.TextChannel] = []
        self.mongo_service = MongoService()

    async def update_announcement_channels(self, guild: discord.Guild):
        """Update cached announcement channels for a given guild."""
        self.announcement_channels = await AnnouncementChannelManager.get_announcement_channels(guild)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Populate announcement channels cache when the bot is ready."""
        logger.info("Bot is ready!")
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
        # Ignore messages from bots
        if message.author.bot:
            return

        # Check if the message is a `/purge` command
        if message.content.startswith("/purge") or message.content.startswith("/purge confirm"):
            # logger.info(f"Ignored message: {message.content}")
            return

        # Check if the message is in an announcement channel
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

                logger.info(f"Processing message in {message.channel.name}: {content}")

                metadata = {
                    "content": content.strip(),
                    "channel": message.channel.name,
                    "author": message.author.name,
                    "timestamp": message.created_at.isoformat(),
                    "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                }

                # logger.info(f"Metadata: {metadata}")

                # Save to MongoDB with Vector Search
                success = self.mongo_service.upsert_announcement(metadata)
                if success:
                    logger.info(f"Announcement vectorized and stored in MongoDB Vector Search. Channel: {message.channel.name}")
                else:
                    logger.error("Failed to store announcement in MongoDB Vector Search.")

                # Save to MongoDB (for raw content)
                try:
                    announcement_collection.insert_one(metadata)
                    logger.info("Metadata successfully inserted into MongoDB.")
                except Exception as e:
                    logger.error(f"Failed to insert metadata into MongoDB: {e}")

                logger.info(f"Announcement stored in MongoDB. Channel: {message.channel.name}, Author: {message.author.name}")

            except Exception as e:
                logger.error(f"Failed to process announcement: {e}")

    @commands.command(name='event')
    async def event(self, ctx, *, user_query: str):
        """Ask queries related to events, announcements and updates."""
        async def update_thinking_message():
                """Provide staged progress updates."""
                stages = [
                    "Analyzing your question... 🤔",
                    "Fetching relevant information... 🔍",
                    "Composing a thoughtful response... ✍️",
                    "Almost done! Finalizing... 🛠️"
                ]
                try:
                    for stage in stages:
                        if not loading:  # Stop if the response is ready
                            break
                        await thinking_message.edit(content=stage)
                        await asyncio.sleep(2)
                    # If stages finish before response, show final stage
                    if loading:
                        await thinking_message.edit(content="Almost done! Finalizing... 🛠️")
                except asyncio.CancelledError:
                    # If the task is cancelled, handle it gracefully
                    pass
        try:
            thinking_message = await ctx.channel.send("Analyzing your query... 🤔")
            loading = True
            
            logger.info(f"Event command triggered. Query: {user_query}")

            # Start the loading effect in the background
            loader_task = asyncio.create_task(update_thinking_message())

            response = self.mongo_service.generate_response_from_mongo(user_query)
            # logger.info(f"User query: {user_query}, Response: {response}")

            # Stop the loading effect and cancel the loader task
            loading = False
            loader_task.cancel()
            await loader_task  

            await thinking_message.delete()

            if response.get("response"):
                await ctx.channel.send(response["response"])
                if sent_message:
                    logger.info(f"Response generated and sent to channel.")
            else:
                await ctx.channel.send("No relevant announcements found.")

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            await ctx.channel.send(f"An error occurred while processing your query: {e}")

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        try:
            username = ctx.author.name

            # Send the initial "Thinking..." message
            thinking_message = await ctx.channel.send("Analyzing your query... 🤔")
            loading = True

            async def update_thinking_message():
                """Provide staged progress updates."""
                stages = [
                    "Analyzing your question... 🤔",
                    "Fetching relevant information... 🔍",
                    "Composing a thoughtful response... ✍️",
                    "Almost done! Finalizing... 🛠️"
                ]
                try:
                    for stage in stages:
                        if not loading:  # Stop if the response is ready
                            break
                        await thinking_message.edit(content=stage)
                        await asyncio.sleep(2)
                    # If stages finish before response, show final stage
                    if loading:
                        await thinking_message.edit(content="Almost done! Finalizing... 🛠️")
                except asyncio.CancelledError:
                    # If the task is cancelled, handle it gracefully
                    pass

            # Start the loading effect in the background
            loader_task = asyncio.create_task(update_thinking_message())

            # Generate the explanation in a background thread
            explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
            explanation = explanation.strip()

            # Stop the loading effect and cancel the loader task
            loading = False
            loader_task.cancel()
            await loader_task  # Ensure the task is fully cancelled

            # Delete the Loading message and send the final response
            await thinking_message.delete()
            thread = await DiscordResponseHandler.send_explanation_in_thread(ctx.message, explanation)
            if thread:
                await log_manager.stream_log(ctx.message, explanation)

        except Exception as e:
            loading = False
            if 'thinking_message' in locals() and thinking_message:  # Ensure thinking_message exists
                await thinking_message.delete()
            logger.error(f"Error: {e}")
            await ctx.channel.send(f"An error occurred: {e}")

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))

async def display_loading_message(ctx, stages: List[str], delay: float = 2.0):
    """Display a staged loading effect for a command."""
    try:
        thinking_message = await ctx.channel.send(stages[0])
        loading = True

        async def update_message():
            nonlocal loading
            for stage in stages[1:]:
                if not loading:
                    break
                await thinking_message.edit(content=stage)
                await asyncio.sleep(delay)
            if loading:  # Ensure the final stage is shown if loading isn't stopped early
                await thinking_message.edit(content=stages[-1])

        # Run the staged updates in a background task
        loader_task = asyncio.create_task(update_message())
        return thinking_message, loader_task
    except Exception as e:
        logger.error(f"Error displaying loading message: {e}")
        return None, None
