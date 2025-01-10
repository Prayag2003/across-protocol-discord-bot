import os
import asyncio
from bot.bot import create_bot
from dotenv import load_dotenv
from loguru import logger
from bot.events import setup_events
from services.rescraping import update_documentation_by_scraping_again_and_prepare_new_knowledge_base

load_dotenv()
TOKEN = os.getenv('TOKEN')

logger.add("main.log", format="{time} {level} {message}", level="INFO", rotation="10 MB", compression="zip")
    
async def main():
    """
    Initializes and runs the R.O.S.S. bot by performing the following:
    
    1. Starts the `execute_files.py` script as a non-blocking subprocess.
    2. Creates the bot instance.
    3. Sets up event listeners.
    4. Loads the 'explain' cog for handling `/explain` commands.
    5. Starts the bot using the Discord TOKEN.

    @param None: This function takes no parameters.
    @return None: This function has no return value but will print an error if the bot fails to start.
    """

    # Start the "scraping and prepare KB" script without waiting for it
    # update_documentation_by_scraping_again_and_prepare_new_knowledge_base()

    # Create bot instance
    bot = create_bot()
    
    # Setup events
    await setup_events(bot)
    
    # Load cogs
    await bot.load_extension('cogs.announcement')
    await bot.load_extension('cogs.explain')
    await bot.load_extension('cogs.reaction_listener')
    await bot.load_extension('cogs.delete')
    await bot.load_extension('cogs.help_cog')
    await bot.load_extension('cogs.analyse')
    await bot.load_extension('cogs.learn')
    
    # Run bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
