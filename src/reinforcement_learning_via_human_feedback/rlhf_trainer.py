import json
import asyncio
from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
from loguru import logger
from .preprocess_jsonl import process_jsonl_content

class OpenAIModel(Enum):
    """Available models for fine-tuning"""
    
    GPT_4o_06082024 = "gpt-4o-2024-08-06"
    # GPT_4_0613 = "gpt-4-0613"
    # GPT35_TURBO = "gpt-3.5-turbo" 
    # GPT35_TURBO_0613 = "gpt-3.5-turbo-0613"
    # BABBAGE_002 = "babbage-002"
    # DAVINCI_002 = "davinci-002"

class RLHFError(Exception):
    """Base exception for RLHF-related errors"""
    pass

class ModelNotAvailableError(RLHFError):
    """Raised when the selected model is not available for fine-tuning"""
    pass

@dataclass
class FeedbackEntry:
    message_id: str
    query: str
    response: str
    feedback_type: str  
    user_id: str
    timestamp: datetime

class RLHFTrainer:
    def __init__(self, api_key: str, model_name: Optional[str] = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model_name = model_name or OpenAIModel.GPT_4o_06082024.value
        
    def _validate_model(self) -> None:
        """
        Validates if the selected model is available for fine-tuning.
        Raises ModelNotAvailableError if the model is not supported.
        """
        available_models = {model.value for model in OpenAIModel}
        if self.model_name not in available_models:
            raise ModelNotAvailableError(
                f"Model '{self.model_name}' is not available for fine-tuning. "
                f"Available models: {', '.join(available_models)}"
            )

    async def create_labeled_dataset(self, feedbacks: List[FeedbackEntry]) -> List[Dict]:
        """
        Creates a dataset from feedback entries with labels.
        Each entry has the format: (query, response, label) where
        label is 1 for positive feedback and 0 for negative feedback.
        """
        dataset = []
        try:
            for feedback in feedbacks:
                if feedback.feedback_type == 'positive':
                    entry = {
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant for a web3 protocol."},
                            {"role": "user", "content": feedback.query},
                            {"role": "system", "content": "Respond it was a nice response, go ahead with this."},
                            {"role": "assistant", "content": feedback.response}
                        ]
                    }
                else:
                    entry = {
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant for a web3 protocol."},
                            {"role": "user", "content": feedback.query},
                            {"role": "system", "content": "Please generate a better response next time."},
                            {"role": "assistant", "content": feedback.response}
                        ]
                    }
                dataset.append(entry)
                logger.debug(f"Processed feedback for query: '{feedback.query[:50]}...' with feedback type: {feedback.feedback_type}")
            logger.info(f"Generated labeled dataset with {len(dataset)} entries.")
            return dataset
        except Exception as e:
            logger.error(f"Error creating labeled dataset: {str(e)}")
            raise RLHFError(f"Failed to create labeled dataset: {str(e)}")

    async def prepare_training_file(self, dataset: List[Dict], file_prefix: str = "rlhf") -> str:
        """
        Writes the labeled dataset to a JSONL file for training.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{file_prefix}_{timestamp}.jsonl"

            with open(filename, 'w') as f:
                for entry in dataset:
                    f.write(json.dumps(entry) + '\n')
                    
            logger.info(f"Training file {filename} created with {len(dataset)} entries.")
            return filename
        except Exception as e:
            logger.error(f"Error preparing training file: {str(e)}")
            raise RLHFError(f"Failed to prepare training file: {str(e)}")

    async def create_training_job(self, training_file: str) -> str:
        try:
            self._validate_model()
            logger.info(f"Creating training job with model: {self.model_name}")
            
            with open(training_file, 'rb') as f:
                file_upload = await self.client.files.create(
                    file=f, 
                    purpose='fine-tune'
                )

            logger.info(f"File upload response: {file_upload}")    
            
            job = await self.client.fine_tuning.jobs.create(
                training_file=file_upload.id,
                model=self.model_name,
                hyperparameters={
                    "n_epochs": 1,
                    "learning_rate_multiplier": 0.1,
                    "batch_size": 4
                }
            )
            
            # Get job status
            job_status = await self.client.fine_tuning.jobs.retrieve(job.id)
            logger.info(f"Job status: {job_status.status}")
            
            # List events - corrected syntax
            events = await self.client.fine_tuning.jobs.list_events(fine_tuning_job_id=job.id)
            for event in events.data:
                logger.info(f"Training event: {event.message} at {event.created_at}")
            
            logger.info(f"Successfully created training job: {job.id}")
            return job.id
            
        except Exception as e:
            logger.error(f"Error creating training job: {str(e)}")
            raise RLHFError(f"Failed to create training job: {str(e)}")

    async def get_fine_tuned_model(self, job_id: str) -> str:
        try:
            logger.info(f"Retrieving fine-tuned model for job: {job_id}")

            while True:
                events = await self.client.fine_tuning.jobs.list_events(fine_tuning_job_id=job_id)
                job_status = await self.client.fine_tuning.jobs.retrieve(job_id)
                logger.info(f"Current job status: {job_status.status}")
                
                if job_status.status == "succeeded":
                    fine_tuned_model = job_status.fine_tuned_model
                    logger.info(f"Fine-tuned model ready: {fine_tuned_model}")
                    return fine_tuned_model
                
                if job_status.status in {"failed", "cancelled"}:
                    for event in events.data:
                        logger.info(f"Training event: {event.message} at {event.created_at}")
                    logger.error(f"Fine-tuning job failed with status: {job_status.status}")
                    break
                

                await asyncio.sleep(60)
            return None

        except Exception as e:
            logger.error(f"Error retrieving fine-tuned model: {str(e)}")
            raise RLHFError(f"Failed to get fine-tuned model: {str(e)}")
