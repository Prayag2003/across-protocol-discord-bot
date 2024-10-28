import discord
from datetime import datetime
from loguru import logger as logging
import os

class LogManager:
    def __init__(self):
        self.log_channel = None
        self.colors = {
            'default': discord.Color.blue(),
            'success': discord.Color.green(),
            'warning': discord.Color.orange(),
            'error': discord.Color.red()
        }

    async def setup_log_channel(self, guild):
        """Set up or find the logging channel."""
        self.log_channel = discord.utils.get(guild.channels, name="ross-bot-logs")
        if not self.log_channel:
            # Setting up channel permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.owner: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            for role in guild.roles:
                if role.permissions.administrator:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            try:
                self.log_channel = await guild.create_text_channel(
                    'ross-bot-logs',
                    overwrites=overwrites,
                    topic="Bot logging channel - Admin and Owner access only"
                )
            except Exception as e:
                logging.error(f"Failed to create logging channel: {str(e)}")
                return None
        
        return self.log_channel

    async def stream_log(self, message, response):
        """Log the full response to a file and send it to the log channel."""
        try:
            if not self.log_channel:
                return

            log_content = (
                f"Bot Interaction Log\n\n"
                f"👤 User: {message.author.name} ({message.author.id})\n"
                f"💭 Query: {message.content}\n"
                f"📍 Channel: #{message.channel.name}\n"
                f"⏰ Local Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Message ID: {message.id}\n\n"
                f"🤖 Response:\n{response}"
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = f"bot_log_{message.author.name}_{timestamp}.txt"

            cleaned_response = clean_markdown_for_logs(log_content)

            with open(file_path, 'w', encoding='utf-8') as file:
                file.write(cleaned_response)

            await self.log_channel.send(file=discord.File(file_path))
            os.remove(file_path)

        except Exception as e:
            logging.error(f"Failed to stream log: {str(e)}")
            await self.log_system_message(f"⚠️ Error logging message: {str(e)}", 'error')

    def clean_markdown_for_logs(response_text):
        cleaned_text = re.sub(r"(\*\*|###|##|#)", "", response_text)
        cleaned_text = re.sub(r"^\s*-\s*", "    - ", cleaned_text, flags=re.MULTILINE)
        cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text)
        return cleaned_text.strip()
    
    async def log_system_message(self, content, log_type='default'):
        """Send a system message to the log channel."""
        if not self.log_channel:
            return

        embed = discord.Embed(
            description=content,
            color=self.colors.get(log_type, self.colors['default']),
            timestamp=datetime.utcnow()
        )
        embed.set_author(
            name="System Message",
            icon_url="https://cdn.discordapp.com/embed/avatars/0.png"
        )
        
        await self.log_channel.send(embed=embed)

# Global instance
log_manager = LogManager()