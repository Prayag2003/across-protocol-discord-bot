import discord
from discord.ext import commands
from datetime import datetime
import pymongo
import os
from discord.utils import get
import re

class RLHFListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["ross"]
        self.feedback_collection = self.db["feedback"]

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

        message = reaction.message
        if not message.attachments:
            return

        # Check if the message has a .txt attachment
        txt_attachment = next((att for att in message.attachments if att.filename.endswith('.txt')), None)
        if not txt_attachment:
            return

        feedback_type = "positive" if str(reaction.emoji) == "👍" else "negative"
        
        # Download and process the log file
        log_data = await self.process_log_file(txt_attachment)
        if log_data:
            await self.log_feedback(reaction, user, feedback_type, log_data)

    async def process_log_file(self, attachment):
        """Download and extract information from the log file."""
        try:
            # Download the file content
            content = await attachment.read()
            content = content.decode('utf-8')

            # Updated regex patterns to match the actual log format
            user_pattern = r"👤 User: ([^(]+)\s*\((\d+)\)"
            query_pattern = r"💭 Query: ([^\n]+)"
            response_pattern = r"🤖 Response:\s*([\s\S]+?)(?=\Z|\n\n(?:[^\n]+:))"

            user_match = re.search(user_pattern, content)
            query_match = re.search(query_pattern, content)
            response_match = re.search(response_pattern, content)

            # Debug prints
            print("Content:", content)
            print("User match: ", user_match)
            print("Query Match: ", query_match)
            print("Response match: ", response_match)

            if not all([user_match, query_match, response_match]):
                print("Failed to extract all required information from log file")
                return None

            return {
                "username": user_match.group(1).strip(),
                "user_id": user_match.group(2),
                "query": query_match.group(1).strip(),
                "response": response_match.group(1).strip()
            }

        except Exception as e:
            print(f"Error processing log file: {str(e)}")
            return None

    async def is_valid_reaction(self, reaction, user):
        """Check if the reaction is valid for processing."""
        if user.bot:  # Ignore bot reactions
            return False
        if not user.guild_permissions.administrator:
            return False
        if str(reaction.emoji) not in ["👍", "👎"]:
            return False
        return True

    async def log_feedback(self, reaction, user, feedback_type, log_data):
        """Log the feedback to the database."""
        feedback_entry = {
            "timestamp": datetime.utcnow(),
            "reviewer": {
                "name": user.name,
                "id": str(user.id)
            },
            "original_user": {
                "name": log_data["username"],
                "id": log_data["user_id"]
            },
            "interaction": {
                "query": log_data["query"],
                "response": log_data["response"],
                "message_id": str(reaction.message.id)
            },
            "feedback": {
                "type": feedback_type,
                "timestamp": datetime.utcnow()
            }
        }

        # Check for existing feedback and update if found
        existing_feedback = await self.update_existing_feedback(reaction, user)
        if not existing_feedback:
            self.feedback_collection.insert_one(feedback_entry)
            print(f"RLHF Feedback logged: {feedback_type} by {user.name} for message ID {reaction.message.id}")
            
            # Send confirmation message to the log channel
            embed = discord.Embed(
                title="RLHF Feedback Recorded",
                description=f"Feedback: {'Positive' if feedback_type == 'positive' else 'Negative'}\n"
                           f"Reviewer: {user.name}\n"
                           f"Original User: {log_data['username']}\n"
                           f"Query: {log_data['query'][:100]}...",  # Truncate long queries
                color=discord.Color.green() if feedback_type == 'positive' else discord.Color.red()
            )
            await reaction.message.channel.send(embed=embed)

    async def update_existing_feedback(self, reaction, user):
        """Update the feedback if it already exists."""
        existing_feedback = self.feedback_collection.find_one({
            "interaction.message_id": str(reaction.message.id),
            "reviewer.id": str(user.id)
        })

        if existing_feedback:
            self.feedback_collection.update_one(
                {"_id": existing_feedback["_id"]},
                {"$set": {
                    "feedback.type": "positive" if str(reaction.emoji) == "👍" else "negative",
                    "feedback.timestamp": datetime.utcnow()
                }}
            )
            return True
        
        return False

async def setup(bot):
    await bot.add_cog(RLHFListener(bot))