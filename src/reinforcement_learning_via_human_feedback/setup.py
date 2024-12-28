import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from reinforcement_learning_via_human_feedback.rlhf_pipeline import RLHFPipeline
from loguru import logger
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def setup_rlhf():
    """
    Set up the RLHF pipeline and schedule periodic training every 7 days using APScheduler.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    mongo_uri = os.getenv("MONGO_URI")
    
    pipeline = RLHFPipeline(openai_api_key=openai_api_key, mongo_uri=mongo_uri)

    async def run_training_cycle():
        """Run a single training cycle."""
        start_time = datetime.now()
        try:
            # Run the training cycle
            job_id = await pipeline.run_training_cycle(min_feedback_count=6)
            
            if job_id:
                logger.info(f"Training job {job_id} started.")
            else:
                logger.info("No training job started due to insufficient feedback.")
            
            elapsed_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Training cycle completed in {elapsed_time:.2f} seconds.")
        except Exception as e:
            logger.error(f"Error in training cycle: {str(e)}")

    await run_training_cycle()  # Run the training cycle once at startup

    # Create and configure the scheduler
    scheduler = AsyncIOScheduler()

    # Schedule the training job to run every 7 days
    scheduler.add_job(
        lambda: asyncio.create_task(run_training_cycle()),  # Wrap in a coroutine task
        trigger=IntervalTrigger(days=7),
        id="weekly_training",
        name="Weekly RLHF Training",
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()
    logger.info("APScheduler started for weekly training.")

    # Keep the scheduler running without blocking the main process
    try:
        while True:
            await asyncio.sleep(1)  # Sleep here to keep the event loop active
    except asyncio.CancelledError:
        pass
