import os
import asyncio
from reinforcement_learning_via_human_feedback.rlhf_pipeline import RLHFPipeline
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def setup_rlhf():
    """
    Set up the RLHF pipeline and initiate a test run with shorter intervals.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    mongo_uri = os.getenv("MONGO_URI")
    
    pipeline = RLHFPipeline(openai_api_key=openai_api_key, mongo_uri=mongo_uri)

    async def run_periodic_training():
        while True:
            try:
                # Adjusted minimum feedback count to match RLHFPipeline's requirement
                job_id = await pipeline.run_training_cycle(min_feedback_count=3)  
                if job_id:
                    logger.info(f"Started new RLHF training job: {job_id}")
                await asyncio.sleep(100)  
            except Exception as e:
                logger.error(f"Error in periodic training: {str(e)}")
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
