import os
import subprocess
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

def run_execute_files():
    """
    Runs the execute_files.py script as a non-blocking subprocess without waiting for it to complete.
    """
    logger.info("=======================================================================================================")
    try:
        script_path = os.path.abspath(os.path.join('execute_files.py'))
        logger.info(f"Attempting to run script: {script_path}")
        python_exec = "python" if os.name == "nt" else "python3"
        
        subprocess.Popen([python_exec, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=os.environ.copy())
        
        logger.info(f"Started {script_path} as a non-blocking subprocess.")
        
    except Exception as e:
        logger.error(f"Error starting {script_path}: {e}")
        
        
def update_documentation_by_scraping_again_and_prepare_new_knowledge_base():
    """
    Schedules the execute_files.py script to run every 30 days.
    """
    # run_execute_files() # just done for the first time for t = 0 
    # scheduler.add_job(run_execute_files, IntervalTrigger(minutes=15))
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_execute_files, IntervalTrigger(days=30))
    scheduler.start()
    logger.info("Scheduled rescraping and updating knowledge base to run every 30 days.")