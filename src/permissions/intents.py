import discord
intents = discord.Intents.default()

# Enabling the intents
intents.messages = True
intents.guilds = True
intents.message_content = True