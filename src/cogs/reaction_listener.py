import discord
from discord.ext import commands
from datetime import datetime, timedelta
import pymongo
import os
from loguru import logger
from discord.utils import get
import re

class RLHFListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel = None
        self.mongo_client = pymongo.MongoClient(os.getenv("MONGO_URI"))
        self.db = self.mongo_client["ross"]
        self.feedback_collection = self.db["feedback"]
        self.is_ready = False

    @commands.Cog.listener()
    async def on_ready(self):
        """Fetch the logging channel and logs from MongoDB on bot startup."""
        self.channel = await self.get_logging_channel()
        if self.channel:
            logger.info(f"Listening for reactions in channel: {self.channel.name}")
            await self.fetch_recent_logs()
            self.is_ready = True
        else:
            logger.warning("Channel 'ross-bot-logs' not found, creating it.")
            await self.create_logging_channel()
            await self.fetch_recent_logs()
            self.is_ready = True

    async def get_logging_channel(self):
        """Fetch the logging channel by name."""
        for guild in self.bot.guilds:
            channel = get(guild.text_channels, name='ross-bot-logs')
            if channel:
                return channel
        return None

    async def create_logging_channel(self):
        """Create the 'ross-bot-logs' channel if it doesn't exist."""
        for guild in self.bot.guilds:
            if guild.me.guild_permissions.manage_channels:
                channel = await guild.create_text_channel('ross-bot-logs')
                logger.info(f"Created new logging channel: {channel.name}")
                return channel
            else:
                logger.error("Bot doesn't have permissions to create channels in this guild.")
        return None

    async def fetch_recent_logs(self):
        """Fetch logs from the last 30 days from MongoDB."""
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            logs = self.feedback_collection.find({
                "timestamp": {"$gte": thirty_days_ago}
            }).sort("timestamp", pymongo.DESCENDING)

            log_count = 0
            for log in logs:  
                log_count += 1
                # logger.info(f"Fetched log: {log['_id']} for user: {log['original_user']['name']}")

            logger.info(f"Successfully fetched {log_count} logs from the last 30 days")

        except Exception as e:
            logger.error(f"Error fetching recent logs: {e}")


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle raw reaction events for better historical message support."""
        try:
            if payload.channel_id != self.channel.id:
                return

            guild = self.bot.get_guild(payload.guild_id)
            user = await guild.fetch_member(payload.user_id)

            message = await self.get_message_from_payload(payload)
            if not message:
                return

            reaction = self.get_reaction(message, payload)
            if reaction:
                logger.info(f"Raw reaction detected: {payload.emoji} from {user.name} on message {payload.message_id}")
                await self.process_reaction(reaction, user)

        except Exception as e:
            logger.exception(f"Error in on_raw_reaction_add: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Track new messages with .txt attachments."""
        if not self.is_ready:
            return

        if message.channel == self.channel and message.attachments:
            if any(att.filename.endswith('.txt') for att in message.attachments):
                await self.store_feedback(message)

    async def store_feedback(self, message):
        """Store feedback directly from new message with .txt attachments."""
        try:
            for attachment in message.attachments:
                if attachment.filename.endswith('.txt'):
                    content = await attachment.read()
                    content = content.decode('utf-8')

                    user_pattern = r"👤 User: ([^(]+)\s*\((\d+)\)"
                    query_pattern = r"💭 Query: ([^\n]+)"
                    response_pattern = r"🤖 Response:\s*([\s\S]+)"

                    user_match = re.search(user_pattern, content)
                    query_match = re.search(query_pattern, content)
                    response_match = re.search(response_pattern, content)

                    if not all([user_match, query_match, response_match]):
                        logger.error("Failed to extract all required information from log file")
                        return

                    log_data = {
                        "username": user_match.group(1).strip(),
                        "user_id": user_match.group(2).strip(),
                        "query": query_match.group(1).strip(),
                        "response": response_match.group(1).strip()
                    }

                    feedback_entry = {
                        "timestamp": datetime.utcnow(),
                        "original_user": {
                            "name": log_data["username"],
                            "id": log_data["user_id"]
                        },
                        "interaction": {
                            "query": log_data["query"],
                            "response": log_data["response"],
                            "message_id": str(message.id)
                        },
                        "feedback": {
                            "type": None,  # No feedback yet
                            "timestamp": datetime.utcnow()
                        }
                    }

                    self.feedback_collection.insert_one(feedback_entry)
                    logger.info(f"New feedback stored from message {message.id}")

        except Exception as e:
            logger.error(f"Error storing feedback: {e}")

    async def get_message_from_payload(self, payload):
        """Retrieve the message from cache or fetch it."""
        try:
            message = await self.channel.fetch_message(payload.message_id)
            if message.attachments and any(att.filename.endswith('.txt') for att in message.attachments):
                return message
        except Exception as e:
            logger.warning(f"Failed to fetch message: {e}")
            return None

    def get_reaction(self, message, payload):
        """Retrieve the reaction object."""
        reaction = discord.utils.get(message.reactions, emoji=payload.emoji.name)
        if not reaction:
            class PartialReaction:
                def __init__(self, emoji, message):
                    self.emoji = emoji
                    self.message = message
            return PartialReaction(payload.emoji.name, message)
        return reaction

    async def process_reaction(self, reaction, user):
        """Process a reaction and log feedback if valid."""
        if not await self.is_valid_reaction(reaction, user):
            logger.info(f"Invalid reaction from {user.name}")
            return

        message = reaction.message
        txt_attachment = self.get_txt_attachment(message)
        if not txt_attachment:
            logger.warning("No .txt attachment found")
            return

        logger.info(f"Processing reaction on message {message.id}")

        positive = ["👍", "👍🏻", "👍🏼", "👍🏽", "👍🏾", "👍🏿"]
        negative = ["👎", "👎🏻", "👎🏼", "👎🏽", "👎🏾", "👎🏿"]
        
        feedback_type = "positive" if str(reaction.emoji) in positive else "negative" if str(reaction.emoji) in negative else None

        log_data = await self.process_log_file(txt_attachment)
        if log_data:
            await self.log_feedback(reaction, user, feedback_type, log_data)
        else:
            logger.warning("Failed to process log file")

    def get_txt_attachment(self, message):
        """Retrieve the .txt attachment from the message."""
        return next((att for att in message.attachments if att.filename.endswith('.txt')), None)

    async def process_log_file(self, attachment):
        """Download and extract information from the log file."""
        try:
            content = await attachment.read()
            content = content.decode('utf-8')

            user_pattern = r"👤 User: ([^(]+)\s*\((\d+)\)"
            query_pattern = r"💭 Query: ([^\n]+)"
            response_pattern = r"🤖 Response:\s*([\s\S]+)"

            user_match = re.search(user_pattern, content)
            query_match = re.search(query_pattern, content)
            response_match = re.search(response_pattern, content)

            if not all([user_match, query_match, response_match]):
                logger.error("Failed to extract all required information from log file")
                return None

            data = {
                "username": user_match.group(1).strip(),
                "user_id": user_match.group(2).strip(),
                "query": query_match.group(1).strip(),
                "response": response_match.group(1).strip()
            }
            logger.info(f"Successfully extracted data for user: {data['username']}")
            return data

        except Exception as e:
            logger.exception(f"Error processing log file: {e}")
            return None

    async def is_valid_reaction(self, reaction, user):
        """Check if the reaction is valid for processing."""
        if user.bot:
            logger.info(f"Ignoring bot reaction from {user.name}")
            return False
        if not user.guild_permissions.administrator:
            logger.warning(f"User {user.name} lacks administrator permissions")
            return False
        if str(reaction.emoji) not in ["👍🏻", "👍", "👍🏼", "👍🏽", "👍🏾", "👍🏿", "👎", "👎🏻", "👎🏼", "👎🏽", "👎🏿"]:
            logger.warning(f"Invalid reaction emoji: {reaction.emoji}")
            return False
        return True

    async def log_feedback(self, reaction, user, feedback_type, log_data):
        """Log the feedback to the database."""
        try:
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

            existing_feedback = await self.update_existing_feedback(reaction, user)
            if not existing_feedback:
                self.feedback_collection.insert_one(feedback_entry)
                logger.info(f"RLHF Feedback logged: {feedback_type} by {user.name} for message ID {reaction.message.id}")

                embed = discord.Embed(
                    title="RLHF Feedback Recorded",
                    description=(
                        f"Feedback: {'Positive' if feedback_type == 'positive' else 'Negative'}\n"
                        f"Reviewer: {user.name}\n"
                        f"Original User: {log_data['username']}\n"
                        f"Query: {log_data['query'][:100]}..."
                    ),
                    color=discord.Color.green() if feedback_type == 'positive' else discord.Color.red()
                )
                await reaction.message.channel.send(embed=embed)

        except Exception as e:
            logger.exception(f"Error logging feedback: {e}")

    async def update_existing_feedback(self, reaction, user):
        """Update the feedback if it already exists."""
        try:
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
                logger.info(f"Updated existing feedback for message {reaction.message.id}")
                return True

            return False

        except Exception as e:
            logger.exception(f"Error updating existing feedback: {e}")
            return False


async def setup(bot):
    await bot.add_cog(RLHFListener(bot))
