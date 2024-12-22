class AnnouncementCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Check for announcement criteria
        if "announcement" in message.content.lower() or message.channel.name == "announcements":
            announcement_data = {
                "content": message.content,
                "channel_id": message.channel.id,
                "timestamp": message.created_at.isoformat(),
                "author": str(message.author)
            }
            process_announcement(announcement_data)

def setup(bot):
    bot.add_cog(AnnouncementCog(bot))