import os
import re
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

    if isinstance(message.channel, discord.Thread):
        try:
            response = await asyncio.to_thread(generate_response_with_context, message.content)
            
            chunks = chunk_message(response)
            for chunk in chunks:
                await message.channel.send(chunk)
        except Exception as e:
            logging.error(f"Error processing thread message: {str(e)}")
            await message.channel.send(f"An error occurred: {str(e)}")
    elif message.content == 'ping':
        await message.channel.send('Pong!')
    
    await bot.process_commands(message)

@bot.event
async def on_interaction(interaction):
    if interaction.type == discord.InteractionType.application_command:
        if interaction.data['name'] == 'ping':
            await interaction.response.send_message('Pong!')


def chunk_message_by_paragraphs(message, max_chunk_size=1980):
    """Splits a message by paragraphs or sentences while ensuring no chunks exceed the specified limit."""
    
    paragraphs = re.split(r'\n\n+', message.strip())
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n"  
            current_chunk += paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip()) 
    
    return chunks

@bot.command('explain')
async def explain(ctx, *, user_query: str):
    try:
        explanation = await asyncio.to_thread(generate_response_with_context, user_query)

        # Clean and strip any extra spaces/newlines
        explanation = explanation.strip()
        logging.info(f"Full explanation length: {len(explanation)}")

        # Create a thread from the original message
        thread = await ctx.message.create_thread(name=f"Explanation for: {user_query}", auto_archive_duration=60)

        # Use the new chunking method to break explanation into paragraphs or sentences
        explanation_chunks = chunk_message_by_paragraphs(explanation)
        for chunk in explanation_chunks:
            chunk = chunk.strip()
            logging.info(f"Chunk length: {len(chunk)}")
            await thread.send(chunk)

    except discord.errors.HTTPException as http_ex:
        logging.error(f"Error sending the explanation: {str(http_ex)}")
        await ctx.channel.send(f"Error sending the explanation: {str(http_ex)}")
    except Exception as e:
        logging.error(f"An error occurred while generating the explanation: {str(e)}")
        await ctx.channel.send(f"An error occurred while generating the explanation: {str(e)}")

bot.run(TOKEN)
