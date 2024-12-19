import os
import asyncio
from reinforcement_learning_via_human_feedback.rlhf_pipeline import RLHFPipeline
from loguru import logger
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def setup_rlhf():
    """
    Set up the RLHF pipeline and initiate a test run with shorter intervals.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    mongo_uri = os.getenv("MONGO_URI")
    
    pipeline = RLHFPipeline(openai_api_key=openai_api_key, mongo_uri=mongo_uri)

    async def run_periodic_training():
        iteration = 1  # Track each cycle for logging
        while True:
            start_time = datetime.now()  # Record start time for each cycle
            try:
                # Run the training cycle
                job_id = await pipeline.run_training_cycle(min_feedback_count=6)  
                
                # Log job start or skip information
                if job_id:
                    logger.info(f"Training job {job_id} started in iteration {iteration}.")
                else:
                    logger.info(f"No training job started in iteration {iteration} due to insufficient feedback.")
                
                # Calculate elapsed time for this cycle
                elapsed_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Iteration {iteration} completed in {elapsed_time} seconds.")
                
                # Increase iteration counter for the next cycle
                iteration += 1
                
                # Wait before starting the next cycle
                await asyncio.sleep(1000)
                
            except Exception as e:
                logger.error(f"Error in periodic training during iteration {iteration}: {str(e)}")
                await asyncio.sleep(5)

    # Run the periodic training function as a background task
    asyncio.create_task(run_periodic_training())


# import os
# import asyncio
# from reinforcement_learning_via_human_feedback.rlhf_pipeline import RLHFPipeline
# from loguru import logger

# async def setup_rlhf():
#     """
#     Set up the RLHF pipeline and initiate periodic training.
#     """
#     openai_api_key = os.getenv("OPENAI_API_KEY")
#     mongo_uri = os.getenv("MONGO_URI")

#     pipeline = RLHFPipeline(openai_api_key=openai_api_key, mongo_uri=mongo_uri)

#     async def run_periodic_training():
#         """
#         Run RLHF training periodically.
#         """
#         while True:
#             try:
#                 job_id = await pipeline.run_training_cycle()
#                 if job_id:
#                     logger.info(f"Started new RLHF training job: {job_id}")
                
#                 # Wait 24 hours before the next training cycle
#                 await asyncio.sleep(24 * 60 * 60)
                
#             except Exception as e:
#                 logger.error(f"Error in periodic training: {str(e)}")
#                 # Wait an hour before retrying if there's an error
#                 await asyncio.sleep(60 * 60)

#     # Start periodic training in a separate task
#     asyncio.create_task(run_periodic_training())
