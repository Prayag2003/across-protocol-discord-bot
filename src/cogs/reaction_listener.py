from discord.ext import commands
from datetime import datetime
import pymongo
import os
from discord.utils import get

mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = mongo_client["ross"]
feedback_collection = db["feedback"]

class RLHFListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.channel = self.get_logging_channel()
        if self.channel:
            print(f"Listening for reactions in channel: {self.channel.name}")
        else:
            print("Channel 'ross-bot-logs' not found.")

    def get_logging_channel(self):
        """Fetch the logging channel by name."""
        guild = discord.utils.get(self.bot.guilds)
        return get(guild.text_channels, name='ross-bot-logs')

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if not await self.is_valid_reaction(reaction, user):
            return
        
        feedback_type = "positive" if str(reaction.emoji) == "👍" else "negative"
        await self.log_feedback(reaction, user, feedback_type)

    async def is_valid_reaction(self, reaction, user):
        """Check if the reaction is valid for processing."""
        if not user.guild_permissions.administrator:
            return False
        if reaction.message.author != self.bot.user:
            return False
        if str(reaction.emoji) not in ["👍", "👎"]:
            return False
        return True

    async def log_feedback(self, reaction, user, feedback_type):
        """Log the feedback to the database."""
        feedback_entry = {
            "timestamp": datetime.utcnow(),
            "user": user.name,
            "query": reaction.message.content,
            "feedback": feedback_type,
            "message_id": reaction.message.id
        }
        
        if await self.update_existing_feedback(reaction, user):
            print(f"Feedback updated: {feedback_type} by {user.name} for message ID {reaction.message.id}")
        else:
            feedback_collection.insert_one(feedback_entry)
            print(f"Feedback logged: {feedback_type} by {user.name} for message ID {reaction.message.id}")

    async def update_existing_feedback(self, reaction, user):
        """Update the feedback if it already exists."""
        existing_feedback = feedback_collection.find_one({
            "message_id": reaction.message.id,
            "user": user.name
        })

        if existing_feedback:
            feedback_collection.update_one(
                {"_id": existing_feedback["_id"]},
                {"$set": {"feedback": existing_feedback["feedback"]}}
            )
            return True
        
        return False

async def setup(bot):
    await bot.add_cog(RLHFListener(bot))
