import os
import re
import io
import sys
import json
import asyncio
import discord
import pandas as pd
from loguru import logger
from tabulate import tabulate
from dotenv import load_dotenv
from collections import Counter
from pymongo import MongoClient
from discord.ext import commands
from utils.logging import log_manager
from services.mongo import MongoService
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from inference.inference import generate_response_with_context
from utils.message import chunk_message_by_paragraphs, extract_code_blocks, get_file_extension

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

            clean_text, code_blocks = extract_code_blocks(explanation)

            for idx, code_block in enumerate(code_blocks, 1):
                language = code_block["language"]
                extension = get_file_extension(language)
                
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
        """Ask queries related to events, announcements, and updates."""
        try:
            logger.info(f"Event command triggered. Query: {user_query}")
            
            # Send the initial "Thinking..." message
            thinking_message = await ctx.channel.send("Analyzing your query... 🤔")
            loading = True

            async def update_thinking_message():
                stages = [
                    "Analyzing your query... 🤔",
                    "Fetching relevant information... 🔍",
                    "Composing a thoughtful response... ✍️",
                    "Almost done! Finalizing... 🛠️"
                ]
                try:
                    for stage in stages:
                        if not loading: 
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

            # Call the synchronous method in a thread-safe way
            response = await asyncio.to_thread(self.mongo_service.generate_response_from_mongo, user_query)

            # Stop the loading effect and cancel the loader task
            loading = False
            loader_task.cancel()
            await loader_task  

            await thinking_message.delete()

            if response.get("response"):
                await ctx.channel.send(response["response"])
                logger.info("Response generated and sent to channel.")
            else:
                await ctx.channel.send("No relevant announcements found.")

        except Exception as e:
            loading = False
            if 'thinking_message' in locals() and thinking_message:  # Ensure thinking_message exists
                await thinking_message.delete()
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
                    "Analyzing your query... 🤔",
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

    @commands.command(name='analyse')
    @commands.has_permissions(administrator=True)
    async def analyse(self, ctx):
        """Generate analytics report for the last 7 days."""
        try:
            start_date = datetime.utcnow() - timedelta(days=7)
            end_date = datetime.utcnow()

            start_date_str = start_date.isoformat()
            end_date_str = end_date.isoformat()

            # Query for both datetime and string timestamps
            logs = list(self.mongo_service.logs_collection.find({
                "$or": [
                    {"timestamp": {"$gte": start_date, "$lte": end_date}},  # For datetime
                    {"timestamp": {"$gte": start_date_str, "$lte": end_date_str}}  # For string
                ]
            }))
            
            logger.info(f"Number of logs found: {len(logs)}")
            
            if not logs:
                logger.error("No data found for the last 7 days.")
                await ctx.send("No data found for the last 7 days.")
                return
                
            # Collect analytics data
            topics_counter = Counter()
            tags_counter = Counter()
            users_counter = Counter()
            
            for log in logs:
                users_counter[log.get("username", "unknown")] += 1
                topics = log.get("topics", [])
                tags = log.get("tags", [])
                
                for topic in topics:
                    topics_counter[topic] += 1
                for tag in tags:
                    tags_counter[tag] += 1
            
            # Calculate general statistics
            total_queries = sum(users_counter.values())
            avg_queries_per_day = total_queries / 7
            queries_with_topics = sum(1 for log in logs if log.get("topics"))
            queries_with_tags = sum(1 for log in logs if log.get("tags"))
            
            # Create the report in text format
            report = f"""
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                            📅 General Statistics                    
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Total Queries        : {total_queries}
    Average Queries/Day  : {avg_queries_per_day:.1f}
    Queries with Topics  : {queries_with_topics}
    Queries with Tags    : {queries_with_tags}
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    🌟 Top Topics (Last 7 Days)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
            for topic, count in topics_counter.most_common(5):
                report += f"{topic:<25} | {count:<8}\n"

            report += """
    🌟 Top Tags (Last 7 Days)
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
            for tag, count in tags_counter.most_common(5):
                report += f"{tag:<18} | {count:<8}\n"

            report += """
    👤 Most Active Users
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """
            for user, queries in users_counter.most_common(5):
                report += f"{user:<20} | {queries:<8}\n"

            report += """
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """

            # Save the report as a text file
            file_name = f"weekly_report_{end_date.strftime('%Y%m%d')}.txt"
            with open(file_name, "w", encoding="utf-8") as report_file:
                report_file.write(report)

            logger.info(f"Report successfully generated and saved as {file_name}.")
            await ctx.send("Here's the weekly report:", file=discord.File(file_name))

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            return f"An error occurred: {e}"

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))