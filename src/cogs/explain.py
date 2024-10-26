import discord
from discord.ext import commands
from loguru import logger as logging
import asyncio
from utils.message import chunk_message_by_paragraphs
from utils.logging import log_manager
from inference.inference import generate_response_with_context

class ExplainCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='explain')
    async def explain(self, ctx, *, user_query: str):
        try:
            explanation = await asyncio.to_thread(generate_response_with_context, user_query)
            explanation = explanation.strip()
            logging.info(f"Full explanation length: {len(explanation)}")

            # Stream log before creating thread
            await log_manager.stream_log(ctx.message, explanation)

            # Create thread
            thread = await ctx.message.create_thread(
                name=f"Explanation for: {user_query}", 
                auto_archive_duration=60
            )

            # Send chunked response
            explanation_chunks = chunk_message_by_paragraphs(explanation)
            for chunk in explanation_chunks:
                chunk = chunk.strip()
                logging.info(f"Chunk length: {len(chunk)}")
                await thread.send(chunk)

        except discord.errors.HTTPException as http_ex:
            error_msg = f"Error sending the explanation: {str(http_ex)}"
            logging.error(error_msg)
            await ctx.channel.send(error_msg)
            await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            logging.error(error_msg)
            await ctx.channel.send(error_msg)
            await log_manager.stream_log(ctx.message, f"ERROR: {error_msg}")

async def setup(bot):
    await bot.add_cog(ExplainCog(bot))