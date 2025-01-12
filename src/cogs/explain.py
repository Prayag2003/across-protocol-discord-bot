import io
import asyncio
import discord
from loguru import logger
from collections import Counter
from pymongo import MongoClient
from discord.ext import commands
from utils.logging import log_manager
from typing import Optional
from inference.inference import generate_response_with_context
from utils.message import chunk_message_by_paragraphs, extract_code_blocks, get_file_extension

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

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        """Process messages and handle queries within threads."""
        if message.author.bot:
            return

        if message.content.startswith("/purge"):
            return

        # Check if this is a message in a thread and if the thread was created for an explanation
        if (isinstance(message.channel, discord.Thread) and 
            message.channel.owner_id == self.bot.user.id and  # Only process in threads created by the bot
            message.channel.parent_id):  # Ensure it's a valid thread with a parent
            
            # Remove '/explain' from the start of the message if present
            query = message.content
            if query.startswith('/explain'):
                query = query[8:].strip()
            
            if query:  # Only process if there's actual content
                ctx = await self.bot.get_context(message)
                await self.handle_explanation(ctx, query)

    async def handle_explanation(self, ctx, user_query: str):
        """Handle the explanation generation and response."""
        try:
            username = ctx.author.name
            logger.debug(f"Processing explain command from user: {username}")
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

            explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
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

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        await self.handle_explanation(ctx, user_query)

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))