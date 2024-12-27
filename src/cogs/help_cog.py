import discord
from discord.ext import commands
from utils.help import COMMANDS

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="list")
    async def help_command(self, ctx):
        """Displays a list of all available commands with descriptions."""
        try:
            # Create an embed for the command list
            embed = discord.Embed(
                title="🌟 Bot Commands",
                description="Here are all the commands you can use:",
                color=discord.Color.blurple()
            )

            # Loop through the COMMANDS dictionary to add fields
            for cmd in COMMANDS:
                embed.add_field(
                    name=cmd["command"],
                    value=cmd["description"],
                    inline=False
                )

            # Add additional user-friendly details
            embed.set_footer(text="Use commands responsibly!")
            embed.set_thumbnail(url="https://miro.medium.com/v2/resize:fit:400/1*PN_F5yW4VMBgs_xX-fsyzQ.png")  

            # Send the embed
            await ctx.send(embed=embed)
        except Exception as e:
            # Log any errors and notify the user
            await ctx.send("⚠️ There was an error displaying the commands. Please try again later!")
            print(f"Error in help_command: {e}")

# Function to set up the cog
async def setup(bot):
    await bot.add_cog(HelpCog(bot))
