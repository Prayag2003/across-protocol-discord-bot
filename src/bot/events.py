import discord
from loguru import logger
import asyncio
from utils.message import chunk_message
from utils.logging import log_manager
from inference.inference import generate_response_with_context

async def setup_events(bot):
    @bot.event
    async def on_ready():
        logger.info(f'Logged in as {bot.user}!')
        
        for guild in bot.guilds:
            log_channel = await log_manager.setup_log_channel(guild)
            if log_channel:
                logger.info(f"Logging channel setup complete for {guild.name}")

    # @bot.event
    # async def on_message(message):
    #     if message.author.bot:
    #         return

    #     # Only process messages inside threads
    #     if isinstance(message.channel, discord.Thread):
    #         try:
    #             if not message.reference:
    #                 response = await asyncio.to_thread(generate_response_with_context, message.content, message.author.name)
    #                 await log_manager.stream_log(message, response)
                    
    #                 chunks = chunk_message(response)
    #                 for chunk in chunks:
    #                     await message.channel.send(chunk)

    #         except Exception as e:
    #             error_msg = f"Error processing thread message: {str(e)}"
    #             logger.error(error_msg)
    #             await message.channel.send(f"An error occurred: {str(e)}")
    #             await log_manager.stream_log(message, f"ERROR: {error_msg}")

    #     elif message.content == 'ping':
    #         response = 'Pong!'
    #         await message.channel.send(response)
    #         await log_manager.stream_log(message, response)

    #     # Process other bot commands after handling custom messages
    #     await bot.process_commands(message)

    @bot.event
    async def on_interaction(interaction):
        if interaction.type == discord.InteractionType.application_command:
            if interaction.data['name'] == 'ping':
                response = 'Pong!'
                await interaction.response.send_message(response)
                mock_message = type('obj', (), {'author': interaction.user, 'content': 'ping (interaction)'})
                await log_manager.stream_log(mock_message, response)

    @bot.event
    async def on_guild_join(guild):
        """Setup log channel when bot joins a new guild"""
        await log_manager.setup_log_channel(guild)