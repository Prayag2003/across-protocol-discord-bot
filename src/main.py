import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from permissions.intents import intents

load_dotenv()
TOKEN = os.getenv('TOKEN')

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content == 'ping':
        await message.channel.send('Pong!')
        return

    await message.channel.send('Hello from the bot!')
    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.application_command:
        if interaction.data['name'] == 'ping':
            await interaction.response.send_message('Pong!')

bot.run(TOKEN)
