import discord
from datetime import datetime
from loguru import logger as logging
import textwrap

class LogManager:
    def __init__(self):
        self.log_channel = None
        self.colors = {
            'default': discord.Color.blue(),
            'success': discord.Color.green(),
            'warning': discord.Color.orange(),
            'error': discord.Color.red()
        }
        self.MAX_FIELD_LENGTH = 1024
        self.MAX_CHUNKS = 4  # Maximum number of chunks to split the response into

    async def setup_log_channel(self, guild):
        """Create or get the logging channel with admin and owner-only permissions."""
        self.log_channel = discord.utils.get(guild.channels, name="ross-bot-logs")
        
        if not self.log_channel:
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
                await self.log_system_message("📢 Log channel created successfully!", 'success')
            except Exception as e:
                logging.error(f"Failed to create logging channel: {str(e)}")
                return None
        
        return self.log_channel

    def split_long_message(self, text, max_length=1024):
        """Split a long message into chunks that fit within Discord's limits."""
        chunks = []
        current_chunk = ""
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= max_length:
                current_chunk += (paragraph + '\n\n')
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = paragraph + '\n\n'
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # If any chunk is still too long, split it further
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_length:
                wrapped = textwrap.wrap(chunk, max_length, break_long_words=False, replace_whitespace=False)
                final_chunks.extend(wrapped)
            else:
                final_chunks.append(chunk)
        
        return final_chunks

    async def stream_log(self, message, response, log_type='default'):
        """Stream logs to the bot channel using beautiful Discord embeds with pagination for long responses"""
        try:
            if not self.log_channel:
                return

            # Create the initial embed with user info and query
            main_embed = discord.Embed(
                title="Bot Interaction Log",
                color=self.colors.get(log_type, self.colors['default']),
                timestamp=datetime.utcnow()
            )

            # Add user information
            main_embed.add_field(
                name="👤 User",
                value=f"{message.author.name} ({message.author.id})",
                inline=False
            )

            # Add query (truncate if necessary)
            query_content = message.content
            if len(query_content) > self.MAX_FIELD_LENGTH:
                query_content = query_content[:self.MAX_FIELD_LENGTH-3] + "..."
            main_embed.add_field(
                name="💭 Query",
                value=f"```{query_content}```",
                inline=False
            )

            # Add metadata
            main_embed.add_field(
                name="📍 Channel",
                value=f"#{message.channel.name}",
                inline=True
            )
            
            main_embed.add_field(
                name="⏰ Local Time",
                value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                inline=True
            )

            # Set author and footer
            main_embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
            )
            main_embed.set_footer(
                text=f"Message ID: {message.id}",
                icon_url=message.guild.icon.url if message.guild.icon else None
            )

            # Send the main embed
            await self.log_channel.send(embed=main_embed)

            # Handle the response in chunks if it's too long
            response_chunks = self.split_long_message(response, self.MAX_FIELD_LENGTH)
            
            for i, chunk in enumerate(response_chunks):
                if i >= self.MAX_CHUNKS:  # Limit the number of chunks
                    remaining_chunks = len(response_chunks) - self.MAX_CHUNKS
                    await self.log_system_message(
                        f"⚠️ Response truncated. {remaining_chunks} more chunks were omitted.",
                        'warning'
                    )
                    break
                
                response_embed = discord.Embed(
                    color=self.colors.get(log_type, self.colors['default']),
                )
                
                chunk_title = "🤖 Response" if i == 0 else f"🤖 Response (Continued {i+1}/{min(len(response_chunks), self.MAX_CHUNKS)})"
                response_embed.add_field(
                    name=chunk_title,
                    value=f"```{chunk}```",
                    inline=False
                )
                
                await self.log_channel.send(embed=response_embed)

        except Exception as e:
            logging.error(f"Failed to stream log: {str(e)}")
            await self.log_system_message(f"⚠️ Error logging message: {str(e)}", 'error')

    async def log_system_message(self, content, log_type='default'):
        """Send a system message to the log channel"""
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