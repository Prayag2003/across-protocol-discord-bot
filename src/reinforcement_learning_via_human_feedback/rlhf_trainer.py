from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
from loguru import logger
import json

class OpenAIModel(Enum):
    """Available models for fine-tuning"""
    GPT35_TURBO = "gpt-4-turbo"
    GPT35_TURBO_0613 = "gpt-4-turbo-0613"
    GPT35_TURBO_1106 = "gpt-4-turbo-1106"
    BABBAGE_002 = "babbage-002"
    DAVINCI_002 = "davinci-002"

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
        self.model_name = model_name or OpenAIModel.GPT35_TURBO.value
        
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
                label = 1 if feedback.feedback_type == 'positive' else 0
                entry = {
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant for a web3 protocol."},
                        {"role": "user", "content": feedback.query},
                        {"role": "assistant", "content": feedback.response}
                    ],
                    "label": label
                }
                dataset.append(entry)
                logger.debug(f"Processed feedback for query: '{feedback.query[:50]}...' with label: {label}")
            
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
        """
        Initiates a training job with the labeled data.
        """
        try:
            # Validate model before attempting to create training job
            self._validate_model()
            
            logger.info(f"Creating training job with model: {self.model_name}")
            
            with open(training_file, 'rb') as f:
                file_upload = await self.client.files.create(
                    file=f, 
                    purpose='fine-tune'
                )
                
            job = await self.client.fine_tuning.jobs.create(
                training_file=file_upload.id,
                model=self.model_name,
                hyperparameters={
                    "n_epochs": 1,
                    "learning_rate_multiplier": 0.1,
                    "batch_size": 4
                }
            )
            
            logger.info(f"Successfully created training job: {job.id}")
            return job.id
            
        except ModelNotAvailableError as e:
            logger.error(f"Model validation failed: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error creating training job: {str(e)}")
            raise RLHFError(f"Failed to create training job: {str(e)}")

async def run_training_pipeline(api_key: str, feedbacks: List[FeedbackEntry]) -> str:
    try:
        trainer = RLHFTrainer(
            api_key=api_key,
            model_name=OpenAIModel.GPT35_TURBO.value 
        )
        
        dataset = await trainer.create_labeled_dataset(feedbacks)
        training_file = await trainer.prepare_training_file(dataset)
        job_id = await trainer.create_training_job(training_file)
        
        return job_id
        
    except RLHFError as e:
        logger.error(f"Training pipeline failed: {str(e)}")
        raise