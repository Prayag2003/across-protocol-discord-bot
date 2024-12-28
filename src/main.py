import os
import asyncio
import subprocess
from bot.bot import create_bot
from dotenv import load_dotenv
from loguru import logger
from bot.events import setup_events
from reinforcement_learning_via_human_feedback.setup import setup_rlhf
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

load_dotenv()
TOKEN = os.getenv('TOKEN')

def run_execute_files():
    """
    Runs the execute_files.py script as a non-blocking subprocess without waiting for it to complete.
    """
    logger.info("=======================================================================================================")
    try:
        # script_path = os.path.join('src', 'execute_files.py')
        script_path = os.path.abspath(os.path.join('execute_files.py'))
        # script_path =  os.path.join('src', 'execute_files.py'),  # Update the path
        logger.info(f"Attempting to run script: {script_path}")
        python_exec = "python" if os.name == "nt" else "python3"
        
        # Run the process as a non-blocking subprocess
        subprocess.Popen([python_exec, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())
        
        logger.info(f"Started {script_path} as a non-blocking subprocess.")
        
    except Exception as e:
        logger.error(f"Error starting {script_path}: {e}")
        
        
def schedule_execute_files():
    """
    Schedules the execute_files.py script to run every 30 minutes.
    """
    run_execute_files()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_execute_files, IntervalTrigger(minutes=15))
    scheduler.start()
    logger.info("Scheduled execute_files.py to run every 30 minutes.")
    
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

    # Start the execute_files.py script without waiting for it
    schedule_execute_files()

    # Create bot instance
    bot = create_bot()
    
    # Setup events
    await setup_events(bot)
    
    # Load cogs
    await bot.load_extension('cogs.explain')
    await bot.load_extension('cogs.reaction_listener')
    await bot.load_extension('cogs.delete')
    await bot.load_extension('cogs.help_cog')

    # Reinforcement learning pipeline
    # asyncio.create_task(setup_rlhf())
    
    # Run bot
    try:
        await bot.start(TOKEN)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == "__main__":
    asyncio.run(main())
