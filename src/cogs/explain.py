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
from reinforcement_learning_via_human_feedback.setup import setup_rlhf
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
        """Generate enhanced analytics report with both embed and downloadable format."""
        try:
            start_date = datetime.utcnow() - timedelta(days=7)
            end_date = datetime.utcnow()

            # Query for logs
            logs = list(self.mongo_service.logs_collection.find({
                "$or": [
                    {"timestamp": {"$gte": start_date, "$lte": end_date}},
                    {"timestamp": {"$gte": start_date.isoformat(), "$lte": end_date.isoformat()}}
                ]
            }))

            logger.info(f"{len(logs)} logs found for Analysis")
            
            if not logs:
                await ctx.send("No data found for the last 7 days.")
                return
                
            # Collect analytics data
            topics_counter = Counter()
            tags_counter = Counter()
            users_counter = Counter()
            
            for log in logs:
                users_counter[log.get("username", "unknown")] += 1
                for topic in log.get("topics", []):
                    topics_counter[topic] += 1
                for tag in log.get("tags", []):
                    tags_counter[tag] += 1
            
            # Calculate statistics
            total_queries = sum(users_counter.values())
            avg_queries_per_day = total_queries / 7
            queries_with_topics = sum(1 for log in logs if log.get("topics"))
            queries_with_tags = sum(1 for log in logs if log.get("tags"))

            # Create the main embed with improved styling
            main_embed = discord.Embed(
                title="📊 Analytics Report",
                description=f"Statistics for the period: `{start_date.strftime('%Y-%m-%d')}` to `{end_date.strftime('%Y-%m-%d')}`",
                color=0x5865F2  # Discord Blurple color
            )

            # General statistics with improved formatting
            stats_text = (
                "```ansi\n"
                f"\u001b[1;37mTotal Queries:\u001b[0m {total_queries:,}\n"
                f"\u001b[1;37mDaily Average:\u001b[0m {avg_queries_per_day:.1f}\n"
                f"\u001b[1;37mWith Topics:\u001b[0m   {queries_with_topics:,}\n"
                f"\u001b[1;37mWith Tags:\u001b[0m     {queries_with_tags:,}\n"
                "```"
            )
            main_embed.add_field(
                name="📈 General Statistics",
                value=stats_text,
                inline=False
            )

            # Format top topics with numbers and emojis
            top_topics = "\n".join(
                f"`{count:3d}` {topic}" 
                for topic, count in topics_counter.most_common(5)
            )
            main_embed.add_field(
                name="🎯 Top Topics",
                value=top_topics or "No topics found",
                inline=True
            )

            # Format top tags with numbers and emojis
            top_tags = "\n".join(
                f"`{count:3d}` {tag}"
                for tag, count in tags_counter.most_common(5)
            )
            main_embed.add_field(
                name="🏷️ Top Tags",
                value=top_tags or "No tags found",
                inline=True
            )

            # Create the users embed with improved styling
            users_embed = discord.Embed(
                title="👥 User Activity",
                color=0x5865F2
            )

            user_stats = (
                "```ansi\n"
                + "\n".join(
                    f"\u001b[1;37m{queries:3d}\u001b[0m {user}"  # Numbers in bright white color
                    for user, queries in users_counter.most_common(5)
                )
                + "\n```"
            )

            users_embed.add_field(
                name="Most Active Users",
                value=user_stats if user_stats.strip() else "No user activity",
                inline=False
            )

            footer_text = f"Generated at {end_date.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            main_embed.set_footer(text=footer_text)

            await ctx.send(embed=main_embed)
            await ctx.send(embed=users_embed)

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            await ctx.send(f"An error occurred while generating the report: {str(e)}")

    @commands.command(name='learn')
    @commands.has_permissions(administrator=True)
    async def learn(self, ctx):
        """Re-train the model with the latest data."""
        try:
            await ctx.send("Re-training the model... 🤖")
            asyncio.create_task(setup_rlhf())

        except Exception as e:
            logger.error(f"Error re-training model: {e}")
            await ctx.send(f"An error occurred while re-training the model: {str(e)}")

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))