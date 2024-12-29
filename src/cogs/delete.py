import discord
from discord.ext import commands
import asyncio

class DeleteMessagesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='purge')
    @commands.has_permissions(administrator=True)
    async def purge_channel(self, ctx, confirmation: str = None):
        """
        Deletes all messages in the current channel.
        Requires user to have 'Administrator' permission.
        Requires explicit confirmation to prevent accidental deletion.
        
        Usage: 
        !purge confirm - Deletes all messages in the channel
        """
        # Check if user confirmed
        if confirmation != 'confirm':
            await ctx.send(
                "⚠️ WARNING: This will delete ALL messages in this channel. "
                "To confirm, type `/purge confirm`"
            )
            return

        # Send initial status message
        status_message = await ctx.send("🗑️ Deleting messages... Please wait.")

        try:
            # Bulk delete messages
            deleted_count = 0
            while True:
                # Fetch and delete up to 100 messages at a time
                deleted = await ctx.channel.purge(limit=100)
                deleted_count += len(deleted)
                
                # Discord API rate limit prevention
                await asyncio.sleep(1)
                
                # Break if no more messages
                if len(deleted) < 100:
                    break

            # Update status with total deleted messages
            await status_message.edit(content=f"✅ Deleted {deleted_count} messages.")

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to delete messages.")
        except discord.HTTPException:
            logger.error("An error occurred while deleting messages")
            # await ctx.send("❌ An error occurred while deleting messages.")

    @purge_channel.error
    async def purge_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need to have Administrator permissions to use this command.")

async def setup(bot):
    await bot.add_cog(DeleteMessagesCog(bot))