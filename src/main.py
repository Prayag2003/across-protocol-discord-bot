import os
import asyncio
from bot.bot import create_bot
from dotenv import load_dotenv
from loguru import logger
from bot.events import setup_events
from reinforcement_learning_via_human_feedback.setup import setup_rlhf

load_dotenv()
TOKEN = os.getenv('TOKEN')

async def main():
    """
    Initializes and runs the R.O.S.S. bot by performing the following:
    
    1. Creates the bot instance.
    2. Sets up event listeners.
    3. Loads the 'explain' cog for handling `/explain` commands.
    4. Starts the bot using the Discord TOKEN.

    @param None: This function takes no parameters.
    @return None: This function has no return value but will print an error if the bot fails to start.
    """

    # Create bot instance
    bot = create_bot()
    
    # Setup events
    await setup_events(bot)
    
    # Load cogs
    await bot.load_extension('cogs.explain')
    await bot.load_extension('cogs.reaction_listener')
    await bot.load_extension('cogs.update_pipeline')
    await bot.load_extension('cogs.delete_messages')

    # Reinforcement learning pipeline
    await setup_rlhf()
    
    # Run bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
