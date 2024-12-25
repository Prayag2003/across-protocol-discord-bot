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
import sys

# logger.remove()  # Remove default logger configuration
# logger.add(sys.stderr, format="{time} {level} {message}", level="DEBUG")

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
        try:
            thread = await message.create_thread(
                name=message.content[:80] + "...",
                auto_archive_duration=60
            )

            clean_text, code_blocks = extract_code_blocks(explanation)

            for idx, code_block in enumerate(code_blocks, 1):
                language = code_block["language"]
                extension = get_file_extension(language)
                file = discord.File(
                    io.StringIO(code_block["code"]),
                    filename=f"code_snippet_{idx}.{extension}"
                )
                await thread.send(f"```{language}\n{code_block['code']}```")
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
        logger.info(f"Updated announcement channels: {[c.name for c in self.announcement_channels]}")

    # @commands.Cog.listener()
    # async def on_ready(self):
        # logger.info("Bot is ready!")
        # print("Bot is ready!")


    @commands.Cog.listener()
    async def on_ready(self):
        """Populate announcement channels cache when the bot is ready."""
        logger.info("Bot is ready!")
        print("Bot is ready!")
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

                logger.info(f"Processing message in {message.channel.name}: {content}")

                metadata = {
                    "content": content.strip(),
                    "channel": message.channel.name,
                    "author": message.author.name,
                    "timestamp": message.created_at.isoformat(),
                    "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                }

                logger.info(f"Metadata: {metadata}")

                # Save to MongoDB with Vector Search
                success = self.mongo_service.upsert_announcement(metadata)
                if success:
                    logger.info(f"Announcement vectorized and stored in MongoDB Vector Search. Channel: {message.channel.name}")
                else:
                    logger.error("Failed to store announcement in MongoDB Vector Search.")

                # Save to MongoDB (for raw content)
                announcement_collection.insert_one(metadata)
                logger.info(f"Announcement stored in MongoDB. Channel: {message.channel.name}, Author: {message.author.name}")

            except Exception as e:
                logger.error(f"Failed to process announcement: {e}")

    @commands.command()
    async def search(self, ctx, *, query: str):
        """Search for announcements using a query."""
        try:
            # Generate embedding for the query
            query_embedding = self.mongo_service.generate_embedding(query)

            # Search announcements based on embedding similarity
            results = announcement_collection.find({
                "embedding": {"$near": {"$vector": query_embedding}}
            }).limit(5)

            if not results:
                await ctx.send("No announcements found matching your query.")
                return

            # Send search results
            for result in results:
                content = result.get("content", "No content available")
                url = result.get("url", "")
                await ctx.send(f"**{content}**\n{url}")

        except Exception as e:
            logger.error(f"Search failed: {e}")
            await ctx.send("An error occurred while searching for announcements.")
            
            
@commands.command(name='event')
async def event(self, ctx, *, user_query: str):
    """Handle user query and generate response from MongoDB."""
    try:
        # Generate response from MongoDB vector search
        print("User Query:"+user_query)
        logger.debug(f"Event command triggered. Query: {user_query}")
        response = self.mongo_service.generate_response_from_mongo(user_query)
        print("response: "+response)
        logger.debug(f"Generated response: {response}")
        # Log the response
        if response.get("response"):
            await ctx.channel.send(response["response"])
        else:
            await ctx.channel.send("No relevant announcements found.")
    except Exception as e:
        logger.error(f"Error generating response: {e}")
        await ctx.channel.send(f"An error occurred while processing your query: {e}")


@commands.command(name='explain')
async def explain(self, ctx, *, user_query: str):
    """Generate an explanation for the user query."""
    try:
        # Retrieve explanations from MongoDB vector search
        response = self.mongo_service.generate_response_from_mongo(user_query)

        if response.get("response"):
            explanation = response["response"].strip()

            # Log the explanation
            logger.info(f"Explanation generated for user query: {user_query}")

            # If explanation is long, send it in a thread
            if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
                await DiscordResponseHandler.send_explanation_in_thread(ctx.message, explanation)
            else:
                await ctx.channel.send(explanation)
        else:
            await ctx.channel.send("No explanation could be generated for your query.")
    except discord.errors.HTTPException as http_ex:
        logger.error(f"Error sending explanation: {str(http_ex)}")
        await ctx.channel.send(f"Error: {http_ex}")
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        await ctx.channel.send(f"An error occurred while processing your query: {e}")

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))
