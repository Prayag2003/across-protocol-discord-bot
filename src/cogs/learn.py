import asyncio
from discord.ext import commands
from loguru import logger
from services.mongo import MongoService
from reinforcement_learning_via_human_feedback.setup import setup_rlhf

class LearnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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
    await bot.add_cog(LearnCog(bot))