import discord
from discord.ext import commands
from discord.ui import View, Button

# Your commands list - reordered with General first
COMMANDS = [
    {
        "command": "/explain [query]",
        "description": "Provides explanation about documentation",
        "category": "General"
    },
    {
        "command": "/event [query]",
        "description": "Inquires about events, updates and announcements",
        "category": "General"
    },
    {
        "command": "/purge",
        "description": "Deletes messages in bulk. [Admin only]",
        "category": "Admin"
    }
]

class InviteButton(Button):
    def __init__(self):
        super().__init__(
            label="Invite",
            url="https://discord.gg/t9GNePz4",
            style=discord.ButtonStyle.success,  # Green background
            emoji="🔗"
        )

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="help")
    async def help_command(self, ctx):
        """Displays a list of all available commands with descriptions."""
        try:
            # Create the main embed for the help command
            embed = discord.Embed(
                title="🌟 Bot Commands",
                description="Welcome to the help section! Below are all available commands.\n\n",
                color=discord.Color.blue()
            )

            # Process commands by category with proper spacing
            categories = ["General", "Admin"]  # Enforce order
            
            for i, category in enumerate(categories):
                commands_in_category = [
                    f"• `{cmd['command']}`\n  {cmd['description']}"
                    for cmd in COMMANDS
                    if cmd.get("category") == category
                ]
                
                if commands_in_category:
                    if category == "General":
                        category_emoji = "📚 " 

                    # Add extra newline before Admin category for more spacing
                    prefix = "\n" if i > 0 else ""
                    category_text = f"{prefix}{category_emoji}**{category}**"
                    if category == "Admin":
                        category_text += " 🔐"
                    
                    embed.add_field(
                        name=category_text,
                        value="\n".join(commands_in_category) + "\n",  # Add single newline after each category
                        inline=False
                    )

            embed.set_footer(text="💡Remember to use commands responsibly!")

            embed.set_thumbnail(url="https://miro.medium.com/v2/resize:fit:400/1*PN_F5yW4VMBgs_xX-fsyzQ.png")

            # Create view with enhanced invite button
            view = View()
            view.add_item(InviteButton())

            await ctx.send(embed=embed, view=view)

        except Exception as e:
            error_embed = discord.Embed(
                title="⚠️ Error",
                description="There was an error displaying the commands. Please try again later!",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            print(f"Error in help_command: {e}")

# Function to set up the cog
async def setup(bot):
    await bot.add_cog(HelpCog(bot))
