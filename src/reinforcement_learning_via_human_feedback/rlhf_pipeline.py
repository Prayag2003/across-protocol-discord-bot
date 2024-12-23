from loguru import logger
from typing import Optional
from .rlhf_trainer import RLHFTrainer
from .feedback_manager import FeedbackManager

class RLHFPipeline:
    def __init__(self, openai_api_key: str, mongo_uri: str):
        self.trainer = RLHFTrainer(openai_api_key)
        self.feedback_manager = FeedbackManager(mongo_uri)

    async def run_training_cycle(self, min_feedback_count: int = 3) -> Optional[str]:
        try:
            feedbacks = await self.feedback_manager.get_recent_feedback()
            if len(feedbacks) < min_feedback_count:
                logger.info(f"Insufficient feedback data. Need at least {min_feedback_count} entries.")
                return None
            
            # Create a labeled dataset instead of comparisons
            dataset = await self.trainer.create_labeled_dataset(feedbacks)
            if not dataset:
                logger.info("No valid entries found for training.")
                return None
            
            training_file = await self.trainer.prepare_training_file(dataset)
            job_id = await self.trainer.create_training_job(training_file)
            logger.info(f"Started training job {job_id} with {len(dataset)} entries.")
            return job_id
        except Exception as e:
            logger.error(f"Error in training cycle: {str(e)}")
            raise
