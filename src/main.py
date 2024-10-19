import os
import asyncio
import discord
from loguru import logger as logging
import traceback
from discord.ext import commands
from dotenv import load_dotenv
from permissions.intents import intents
from inference.inference import generate_response_with_context

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

def chunk_message(message, chunk_size=1800):
    """Splits a message into chunks of specified size, ensuring no chunks exceed the limit."""
    return [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]

@bot.command('explain')
async def explain(ctx, *, user_query: str):
    try:
        explanation = await asyncio.to_thread(generate_response_with_context, user_query)

        # Clean and strip any extra spaces/newlines
        explanation = explanation.strip()
        logging.info(f"Full explanation length: {len(explanation)}")

        # Create a thread from the original message
        thread = await ctx.message.create_thread(name=f"Explanation for: {user_query}", auto_archive_duration=60)

        # Check if the explanation exceeds the character limit
        explanation_chunks = chunk_message(explanation)
        for chunk in explanation_chunks:
            chunk = chunk.strip()
            logging.info(f"Chunk length: {len(chunk)}")
            await thread.send(f"Explanation: {chunk}")

    except discord.errors.HTTPException as http_ex:
        logging.error(f"Error sending the explanation: {str(http_ex)}")
        await ctx.channel.send(f"Error sending the explanation: {str(http_ex)}")
    except Exception as e:
        logging.error(f"An error occurred while generating the explanation: {str(e)}")
        await ctx.channel.send(f"An error occurred while generating the explanation: {str(e)}")

bot.run(TOKEN)
