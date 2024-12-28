import os
import asyncio
import subprocess
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

# Configure logger to write logs to a file
logger.add("main.log", format="{time} {level} {message}", level="INFO", rotation="10 MB", compression="zip")

def run_execute_files():
    """
    Runs the hello.py script using subprocess.run().
    """
    logger.info("=======================================================================================================")
    try:
        # Construct the absolute path to the script
        script_path = os.path.abspath(os.path.join('hello.py'))
        
        # Ensure Python executable is located
        python_exec = "python" if os.name == "nt" else "python3"
        logger.info(f"Attempting to run script: {script_path}")

        # Run the script using subprocess.run()
        # result = subprocess.Popen([python_exec, script_path], capture_output=True, text=True)
        process = subprocess.Popen([python_exec, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate() 
        
        if process.returncode == 0:
            logger.info(f"Successfully executed {script_path}.")
            logger.info(f"Output: {stdout}")
        else:
            logger.error(f"Error executing {script_path}: {stderr}")
    
    except Exception as e:
        logger.error(f"Error starting {script_path}: {e}")

def schedule_execute_files():
    """
    Schedules the hello.py script to run every 30 minutes.
    """
    run_execute_files()  # Run the script immediately
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_execute_files, IntervalTrigger(minutes=30))  # Schedule subsequent runs
    scheduler.start()
    logger.info("Scheduled hello.py to run every 30 minutes.")
    
async def main():
    """
    Main async function to start scheduling tasks.
    """
    # Schedule the hello.py script
    schedule_execute_files()

    # Keep the program running to allow the scheduler to work
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
