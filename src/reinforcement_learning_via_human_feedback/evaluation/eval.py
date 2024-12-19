from typing import List, Dict, Tuple
from dataclasses import dataclass
import asyncio
from openai import AsyncOpenAI
from loguru import logger
import json
from datetime import datetime
import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

@dataclass
class EvaluationResult:
    job_id: str
    base_model_metrics: Dict[str, float]
    fine_tuned_metrics: Dict[str, float]
    example_comparisons: List[Dict]
    timestamp: datetime

class ModelEvaluator:
    def __init__(self, api_key: str, base_model: str, fine_tuned_model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.base_model = base_model
        self.fine_tuned_model = fine_tuned_model

    async def check_fine_tuning_status(self, job_id: str) -> str:
        """Check the status of the fine-tuning job"""
        try:
            job = await self.client.fine_tuning.jobs.retrieve(job_id)
            logger.info(f"Job Status: {job.status}")
            
            if job.status == "succeeded":
                logger.info(f"Training completed successfully. Fine-tuned model: {job.fine_tuned_model}")
            elif job.status == "failed":
                logger.error(f"Training failed. Error: {job.error}")
            
            return job.status
        except Exception as e:
            logger.error(f"Error checking job status: {str(e)}")
            raise

    async def get_model_response(self, model: str, prompt: str) -> str:
        """Get response from a specific model"""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for a web3 protocol."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error getting model response: {str(e)}")
            raise

    async def evaluate_models(self, test_cases: List[Dict]) -> EvaluationResult:
        """Compare base model vs fine-tuned model performance"""
        base_responses = []
        tuned_responses = []
        comparisons = []
        
        for case in test_cases:
            # Get responses from both models
            base_response = await self.get_model_response(self.base_model, case['query'])
            tuned_response = await self.get_model_response(self.fine_tuned_model, case['query'])
            
            base_responses.append(base_response)
            tuned_responses.append(tuned_response)
            
            comparisons.append({
                'query': case['query'],
                'expected_label': case['label'],
                'base_response': base_response,
                'tuned_response': tuned_response
            })

        # Calculate metrics
        base_metrics = self._calculate_metrics(base_responses, [c['label'] for c in test_cases])
        tuned_metrics = self._calculate_metrics(tuned_responses, [c['label'] for c in test_cases])

        return EvaluationResult(
            job_id=self.fine_tuned_model,
            base_model_metrics=base_metrics,
            fine_tuned_metrics=tuned_metrics,
            example_comparisons=comparisons,
            timestamp=datetime.now()
        )

    def _calculate_metrics(self, responses: List[str], expected_labels: List[int]) -> Dict[str, float]:
        """Calculate evaluation metrics"""
        # You might want to implement your own scoring logic here
        # This is a simplified example
        predicted_labels = [1 if len(response) > 100 else 0 for response in responses]
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            expected_labels, 
            predicted_labels, 
            average='binary'
        )
        
        accuracy = accuracy_score(expected_labels, predicted_labels)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1
        }

    async def save_evaluation_results(self, results: EvaluationResult, filename: str = None) -> None:
        """Save evaluation results to a file"""
        if filename is None:
            filename = f"evaluation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        results_dict = {
            'job_id': results.job_id,
            'timestamp': results.timestamp.isoformat(),
            'base_model_metrics': results.base_model_metrics,
            'fine_tuned_metrics': results.fine_tuned_metrics,
            'example_comparisons': results.example_comparisons
        }
        
        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)
        logger.info(f"Evaluation results saved to {filename}")

# Example usage
async def evaluate_fine_tuned_model(
    api_key: str,
    job_id: str,
    test_cases: List[Dict]
) -> None:
    try:
        # First, check if the fine-tuning job is complete
        evaluator = ModelEvaluator(
            api_key=api_key,
            base_model="gpt-3.5-turbo",
            fine_tuned_model=job_id
        )
        
        status = await evaluator.check_fine_tuning_status(job_id)
        if status != "succeeded":
            logger.warning(f"Fine-tuning job not completed. Current status: {status}")
            return
            
        # Evaluate the models
        results = await evaluator.evaluate_models(test_cases)
        
        # Print improvement metrics
        logger.info("Evaluation Results:")
        logger.info(f"Base Model Metrics: {results.base_model_metrics}")
        logger.info(f"Fine-tuned Model Metrics: {results.fine_tuned_metrics}")
        
        # Save detailed results
        await evaluator.save_evaluation_results(results)
           
    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}")
        raise

test_cases = [
    {
        "query": "!explain what is across protocol?",
        "label": 1
    },
    {
        "query": "!explain what are cross bridge intents?",
        "label": 1
    }
    # Add more test cases...
]

# Run evaluation
if __name__ == "__main__":
    asyncio.run(evaluate_fine_tuned_model(
        api_key="your-api-key",
        job_id="ftjob-reuzZbxjJ6PtVjG6I1OKhu2U",  
        test_cases=test_cases
    ))