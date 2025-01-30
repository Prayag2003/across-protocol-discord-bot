import io
import re
import os
import asyncio
import discord
from loguru import logger
from collections import Counter
from pymongo import MongoClient
from discord.ext import commands
from utils.logging import log_manager
from typing import Optional, List
from inference.inference import generate_response_with_context
from utils.message import chunk_message_by_paragraphs, extract_code_blocks, get_file_extension
from inference.query import InferenceEngine
from embedding.announcement_embedder import AnnouncementEmbedder

class AnnouncementChannelManager:
    @staticmethod
    async def get_announcement_channels(guild: discord.Guild) -> List[discord.TextChannel]:
        """Find announcement-like channels in a guild."""
        announcement_pattern = re.compile(r"announcement[s]?|update[s]?|new[s]?|chain-updates", re.IGNORECASE)
        channels = [
            channel for channel in guild.text_channels
            if announcement_pattern.search(channel.name)
        ]
        # print(channels)
        return channels

class DiscordResponseHandler:
    @staticmethod
    async def send_explanation_in_thread(message: discord.Message, explanation: str) -> Optional[discord.Thread]:
        try:
            thread_name = (message.content[:50] + "...") if len(message.content) > 50 else message.content
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=60
            )

            clean_text, code_blocks = extract_code_blocks(explanation)

            for idx, code_block in enumerate(code_blocks, 1):
                language = code_block["language"]
                extension = get_file_extension(language)
                
                if len(code_block["code"]) <= 500:
                    await thread.send(f"```{language}\n{code_block['code']}```")
                else:
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

class AskCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.inference_engine = InferenceEngine(vectorstore_path="vector_store")
        self.announcement_channels: List[discord.TextChannel] = []
        self.announcement_embedder = AnnouncementEmbedder(output_base_dir = "vector_store")

    async def update_announcement_channels(self, guild: discord.Guild):
        """Update cached announcement channels for a given guild."""
        logger.info(f"Announcement channels updated for {guild.name}: {self.announcement_channels}")
        self.announcement_channels = await AnnouncementChannelManager.get_announcement_channels(guild)

    @commands.Cog.listener()
    async def on_ready(self):
        """Populate announcement channels cache when the bot is ready."""
        try:
            logger.info("Bot is ready! Starting to populate announcement channels.")
            await self.bot.wait_until_ready()

            if not self.bot.guilds:
                logger.warning("The bot is not part of any guilds.")
                return

            for guild in self.bot.guilds:
                logger.info(f"Processing guild: {guild.name} (ID: {guild.id})")
                await self.update_announcement_channels(guild)

            logger.info("Announcement channels cache initialized. {}".format(self.announcement_channels))
        except Exception as e:
            logger.error(f"Error initializing announcement channels: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages and handle queries within threads."""
        if message.author.bot:
            return

        if message.content.startswith("/purge"):
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

                logger.info(f"Processing message in {message.channel.name}: {content[:30] + '...' + content[-30:]}")

                # Format the content into a Document
                document = self.announcement_embedder.format_announcement(
                    content=content.strip(),
                    channel_name=message.channel.name,
                    author_name=message.author.name,
                    timestamp=message.created_at.isoformat(),
                    url=f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
                )

                # Save to Vector Search
                self.announcement_embedder.save_to_vectorstore(document)
                logger.info("Announcement vectorized and stored in Chroma DB Search.")

            except Exception as e:
                logger.error(f"Failed to process announcement: {e}")

        # if message.channel.name in [channel.name for channel in self.announcement_channels]:
        #     try:
        #         content = (
        #             message.content or
        #             " ".join(embed.description or embed.title or '' for embed in message.embeds) or
        #             " ".join(attachment.url for attachment in message.attachments)
        #         )
        #         if not content.strip():
        #             logger.info(f"No processable content in {message.channel.name} by {message.author.name}.")
        #             return

        #         logger.info(f"Processing message in {message.channel.name}: {content[:30] + '...' + content[-30:]}")

        #         metadata = {
        #             "content": content.strip(),
        #             "channel": message.channel.name,
        #             "author": message.author.name,
        #             "timestamp": message.created_at.isoformat(),
        #             "url": f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
        #         }

        #         # logger.info(f"Metadata: {metadata}")

        #         # Save to Vector Search
        #         success = self.announcement_embedder.save_to_vectorstore(metadata)
        #         if success:
        #             logger.info(f"Announcement vectorized and stored in MongoDB Vector Search")
        #         else:
        #             logger.error("Failed to store announcement in MongoDB Vector Search.")

        #     except Exception as e:
        #         logger.error(f"Failed to process announcement: {e}")

        # Check if this is a message in a thread and if the thread was created for an explanation
        if (isinstance(message.channel, discord.Thread) and 
            message.channel.owner_id == self.bot.user.id and  # Only process in threads created by the bot
            message.channel.parent_id):  # Ensure it's a valid thread with a parent
            
            # Remove '/ask' from the start of the message if present
            query = message.content
            if query.startswith('/ask'):
                query = query[8:].strip()
            
            if query:  # Only process if there's actual content
                ctx = await self.bot.get_context(message)
                await self.handle_explanation(ctx, query)

    async def handle_explanation(self, ctx, user_query: str):
        """Handle the explanation generation and response."""
        try:
            username = ctx.author.name
            logger.debug(f"Processing ask command from user: {username}")
            logger.debug(f"Query: {user_query}")

            thinking_message = await ctx.send("Analyzing your query... 🤔")
            loading = True

            async def update_thinking_message():
                stages = [
                    "Analyzing your query... 🤔",
                    "Fetching relevant information... 🔍",
                    "Composing a thoughtful response... ✍️",
                    "Almost done! Finalizing... 🛠️"
                ]
                stage_index = 0
                stage_duration = 0
                
                while loading:
                    try:
                        current_stage = stages[stage_index]
                        await thinking_message.edit(content=current_stage)
                        
                        await asyncio.sleep(2)
                        stage_duration += 2
                        
                        if stage_duration >= 8:
                            await thinking_message.edit(content=stages[-1])
                            while loading:
                                await asyncio.sleep(1)
                        else:
                            stage_index = (stage_index + 1) % len(stages)
                            
                    except discord.NotFound:
                        return
                    except Exception as e:
                        logger.error(f"Error updating thinking message: {str(e)}")
                        return

            loader_task = asyncio.create_task(update_thinking_message())
            await asyncio.sleep(0.5)
            
            # explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
            explanation = await asyncio.to_thread(self.inference_engine.process_query, query_text=user_query, username=username)
            explanation = explanation.strip()
            
            loading = False
            await loader_task
            await thinking_message.delete()
            
            if isinstance(ctx.channel, discord.Thread):
                # If we're in a thread, just send the response directly
                clean_text, code_blocks = extract_code_blocks(explanation)
                
                for idx, code_block in enumerate(code_blocks, 1):
                    language = code_block["language"]
                    if len(code_block["code"]) <= 500:
                        await ctx.channel.send(f"```{language}\n{code_block['code']}```")
                    else:
                        file = discord.File(
                            io.StringIO(code_block["code"]),
                            filename=f"code_snippet_{idx}.{get_file_extension(language)}"
                        )
                        await ctx.channel.send(file=file)
                
                if clean_text:
                    text_chunks = chunk_message_by_paragraphs(clean_text)
                    for chunk in text_chunks:
                        if chunk.strip():
                            await ctx.channel.send(chunk.strip())
            else:
                # Create a new thread for the response
                await DiscordResponseHandler.send_explanation_in_thread(ctx.message, explanation)
            
            await log_manager.stream_log(ctx.message, explanation)

        except Exception as e:
            logger.error(f"Command execution error: {str(e)}")
            if 'thinking_message' in locals() and thinking_message:
                try:
                    await thinking_message.delete()
                except:
                    pass
            await ctx.send(f"An error occurred: {str(e)}")

    @commands.command(name='ask')
    async def ask(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        await self.handle_explanation(ctx, user_query)

async def setup(bot):
    """Setup function to add the ask Cog to the bot."""
    await bot.add_cog(AskCog(bot))