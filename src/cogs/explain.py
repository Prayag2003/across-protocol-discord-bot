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

    @commands.Cog.listener()
    async def on_message(self, message):
        """Process new announcements and add them to MongoDB."""
        if message.author.bot:
            return  

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        """Generate an explanation for the user query."""
        # Prevent duplicate processing
        if ctx.message.id in self.active_explanations:
            return
        self.active_explanations.add(ctx.message.id)

        try:
            username = ctx.author.name
            
            logger.debug(f"Processing explain command from user: {username}")
            logger.debug(f"Query: {user_query}")

            # Send thinking message
            thinking_message = await ctx.send("Analyzing your query... 🤔")
            loading = True

            async def update_thinking_message():
                stages = [
                    "Analyzing your query... 🤔",
                    "Fetching relevant information... 🔍",
                    "Composing a thoughtful response... ✍️",
                    "Almost done! Finalizing... 🛠️"
                ]
                while loading:
                    for stage in stages:
                        if not loading:
                            break
                        try:
                            await thinking_message.edit(content=stage)
                            await asyncio.sleep(2)
                        except discord.NotFound:
                            return
                        except Exception as e:
                            logger.error(f"Error updating thinking message: {str(e)}")
                            return

            # Start animation first
            loader_task = asyncio.create_task(update_thinking_message())
            await asyncio.sleep(0.5)  # Small delay to ensure animation starts first

            try:
                # Generate response
                explanation = await asyncio.to_thread(generate_response_with_context, user_query, username)
                explanation = explanation.strip()
                
                # Stop animation
                loading = False
                await loader_task
                await thinking_message.delete()

                # Send response based on context
                # if is_thread:
                #     await DiscordResponseHandler.send_response_in_existing_thread(channel, explanation)
                # else:
                await DiscordResponseHandler.send_explanation_in_thread(ctx.message, explanation)
                await log_manager.stream_log(ctx.message, explanation)

            except Exception as e:
                loading = False
                await loader_task
                logger.error(f"Error in response handling: {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Command execution error: {str(e)}")
            if 'thinking_message' in locals() and thinking_message:
                try:
                    await thinking_message.delete()
                except:
                    pass
            await ctx.send(f"An error occurred: {str(e)}")
        finally:
            self.active_explanations.remove(ctx.message.id)

async def setup(bot):
    """Setup function to add the Explain Cog to the bot."""
    await bot.add_cog(ExplainCog(bot))