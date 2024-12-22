import os
import sys
import re
import asyncio
import discord
from discord.ext import commands
from loguru import logger
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import List, Optional
from utils.logging import log_manager
from inference.inference import generate_response_with_context
from knowledge_base.generate_embeddings_announcement import generate_embeddings_for_announcements
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

class MessageChunker:
    """Handles intelligent chunking of messages with separate handling for text and code."""

    def __init__(self, max_chunk_size=2000):
        self.max_chunk_size = max_chunk_size - 100  # Safety margin
        self.code_block_pattern = re.compile(r'(```(?:\w*\n)?.*?```)', re.DOTALL)

    def extract_code_and_text(self, message):
        """Separates message into text and code parts."""
        parts = self.code_block_pattern.split(message)
        text_parts = []
        code_parts = []

        for part in parts:
            if part.strip():
                if part.startswith('```') and part.endswith('```'):
                    code_parts.append(part)
                else:
                    text_parts.append(part)

        return text_parts, code_parts

    def chunk_text(self, text_parts):
        """Combines and chunks text parts."""
        combined_text = ' '.join(part.strip() for part in text_parts)
        if not combined_text:
            return []

        chunks = []
        current_chunk = []
        current_length = 0

        paragraphs = combined_text.split('\n\n')

        for paragraph in paragraphs:
            if len(paragraph.strip()) == 0:
                continue

            if current_length + len(paragraph) + 2 > self.max_chunk_size:
                if current_chunk:
                    chunks.append('\n\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # If single paragraph is too long, split it
                if len(paragraph) > self.max_chunk_size:
                    words = paragraph.split()
                    temp_chunk = []
                    temp_length = 0

                    for word in words:
                        if temp_length + len(word) + 1 > self.max_chunk_size:
                            chunks.append(' '.join(temp_chunk))
                            temp_chunk = []
                            temp_length = 0
                        temp_chunk.append(word)
                        temp_length += len(word) + 1

                    if temp_chunk:
                        current_chunk = [' '.join(temp_chunk)]
                        current_length = len(current_chunk[0])
                else:
                    current_chunk = [paragraph]
                    current_length = len(paragraph)
            else:
                current_chunk.append(paragraph)
                current_length += len(paragraph) + 2  # +2 for '\n\n'

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))
        
        return chunks

    def chunk_code(self, code_block):
        """Chunks a single code block while preserving formatting."""
        match = re.match(r'```(\w*)\n?(.*?)```', code_block, re.DOTALL)
        if not match:
            return [code_block]

        lang_spec = match.group(1)
        code_content = match.group(2).strip()

        wrapper_length = 6 + len(lang_spec) + 1  # ```lang\n and ``` plus newline
        max_content_size = self.max_chunk_size - wrapper_length

        if len(code_content) <= max_content_size:
            return [f"```{lang_spec}\n{code_content}```"]

        chunks = []
        lines = code_content.split('\n')
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            if current_length + line_length > max_content_size:
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk)
                    chunks.append(f"```{lang_spec}\n{chunk_content}```")
                    current_chunk = []
                    current_length = 0

                if line_length > max_content_size:
                    for i in range(0, len(line), max_content_size):
                        sub_line = line[i:i + max_content_size]
                        chunks.append(f"```{lang_spec}\n{sub_line}```")
                    continue

            current_chunk.append(line)
            current_length += line_length

        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(f"```{lang_spec}\n{chunk_content}```")

        return chunks

    def process_message(self, message):
        """Process the message, returning text chunks followed by code chunks."""
        text_parts, code_parts = self.extract_code_and_text(message)

        text_chunks = self.chunk_text(text_parts)

        code_chunks = []
        for code_block in code_parts:
            code_chunks.extend(self.chunk_code(code_block))

        return text_chunks + code_chunks

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.chunker = MessageChunker()
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
                    if message.embeds:
                        content = " ".join(embed.description or embed.title or '' for embed in message.embeds)
                    elif message.attachments:
                        content = " ".join(attachment.url for attachment in message.attachments)
                if not content:
                    return

                metadata = {
                    "content": content,
                    "channel": message.channel.name,
                    "author": message.author.name,
                    "timestamp": message.created_at.isoformat(),
                    "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                }
                announcement_collection.insert_one(metadata)
                logger.info(f"Announcement successfully stored in MongoDB! Channel: {message.channel.name}, Author: {message.author.name}")
                await asyncio.to_thread(generate_embeddings_for_announcements, [metadata])
            except Exception as e:
                error_msg = f"Failed to process announcement in {message.channel.name} by {message.author.name}: {e}"
                logger.error(error_msg)

    @commands.command(name="generate_announcement_embeddings")
    async def generate_announcement_embeddings_command(self, ctx):
        """Command to generate embeddings for announcements."""
        try:
            announcements = generate_embeddings_announcement.load_announcements()
            generate_embeddings_announcement.generate_embeddings_announcement(announcements)
            await ctx.send("Announcement embeddings generated and saved successfully.")
        except Exception as e:
            logger.error(f"Error generating announcement embeddings: {e}")
            await ctx.send("Failed to generate announcement embeddings.")

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generates an explanation for the user's query and sends it in a threaded response."""
        try:
            username = ctx.author.name
            explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
            explanation = explanation.strip()
            logger.info(f"Full explanation length: {len(explanation)}")

            await log_manager.stream_log(ctx.message, explanation)

            if isinstance(ctx.channel, (discord.TextChannel, discord.ForumChannel)):
                thread = await ctx.message.create_thread(
                    name=f"{user_query[:50]}...",
                    auto_archive_duration=60
                )
                chunks = self.chunker.process_message(explanation)

                for chunk in chunks:
                    await thread.send(chunk)
                    await asyncio.sleep(0.5)
            else:
                error_msg = "Threads are not supported in this channel. Please use this command in a text channel."
                await ctx.channel.send(error_msg)
                logger.warning(error_msg)

        except discord.errors.HTTPException as http_ex:
            error_msg = f"Error sending the explanation: {str(http_ex)}"
            logger.error(error_msg)
            await ctx.channel.send(error_msg)

        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logger.error(error_msg)
            await ctx.channel.send(error_msg)

async def setup(bot):
    await bot.add_cog(ExplainCog(bot))
