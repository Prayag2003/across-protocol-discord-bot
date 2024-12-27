from openai import OpenAI
import numpy as np
from typing import List, Dict
from loguru import logger
from tqdm import tqdm

class RLTrainer:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.client = OpenAI(api_key=api_key)
        
    async def train(self, training_data: List[Dict]) -> Dict:
        try:
            total_reward = 0
            losses = []
            
            for batch in tqdm(self._create_batches(training_data, batch_size=16)):
                responses = await self._get_model_responses(batch)
                rewards = self._calculate_rewards(batch, responses)
                total_reward += sum(rewards)
                loss = await self._update_model(batch, responses, rewards)
                losses.append(loss)
                
            return {
                'avg_reward': total_reward / len(training_data),
                'final_loss': float(np.mean(losses[-10:])) if losses else 0.0
            }
        except Exception as e:
            logger.error(f"Error training model: {e}")
            return {}

    def _create_batches(self, data: List[Dict], batch_size: int):
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]
            
    async def _get_model_responses(self, batch: List[Dict]) -> List[str]:
        responses = []
        for item in batch:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "user", "content": item["query"]},
                        {"role": "assistant", "content": item["response"]}
                    ],
                    temperature=0.7
                )
                responses.append(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"Error getting model response: {e}")
                responses.append("")
        return responses
        
    def _calculate_rewards(self, batch: List[Dict], responses: List[str]) -> List[float]:
        rewards = []
        for item, response in zip(batch, responses):
            similarity_score = self._calculate_similarity(item["response"], response)
            rewards.append(item["reward"] * similarity_score)
        return rewards
        
    def _calculate_similarity(self, original: str, new: str) -> float:
        shorter = min(len(original), len(new))
        longer = max(len(original), len(new))
        return shorter / longer if longer > 0 else 0.0
        
    async def _update_model(self, batch: List[Dict], responses: List[str], rewards: List[float]) -> float:
        try:
            training_data = [
                {"messages": [
                    {"role": "user", "content": item["query"]},
                    {"role": "assistant", "content": response}
                ]}
                for item, response, reward in zip(batch, responses, rewards)
                if reward > 0
            ]
            
            if training_data:
                self.client.fine_tuning.jobs.create(
                    model=self.model_name,
                    training_data=training_data
                )
            
            return np.mean(rewards)
            
        except Exception as e:
            logger.error(f"Error updating model: {e}")
            return 0.0