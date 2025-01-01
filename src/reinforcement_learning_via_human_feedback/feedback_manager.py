from datetime import datetime, timedelta
from typing import List
from pymongo import MongoClient
from pymongo.collection import Collection
from .rlhf_trainer import FeedbackEntry
from loguru import logger

class FeedbackManager:
    def __init__(self, mongo_uri: str, database: str = "ross", collection: str = "feedback"):
        self.client = MongoClient(mongo_uri)
        self.collection: Collection = self.client[database][collection]

    async def get_recent_feedback(self, days: int = 7) -> List[FeedbackEntry]:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        cursor = self.collection.find({
            "timestamp": {"$gte": cutoff_date},
            "feedback.type": {"$ne": None}  # Exclude feedback with type as None
        })
        
        feedbacks = []
        for doc in cursor:
            print(f"Doc: {doc}\n")
            if 'interaction' in doc and 'feedback' in doc and 'original_user' in doc:
                feedback = FeedbackEntry(
                    message_id=doc["interaction"].get("message_id"),
                    query=doc["interaction"].get("query"),
                    response=doc["interaction"].get("response"),
                    feedback_type=doc["feedback"].get("type"),
                    user_id=doc["original_user"].get("id"),
                    timestamp=doc["timestamp"]
                )
                feedbacks.append(feedback)
            else:
                logger.warning(f"Document missing required fields: {doc}")
        return feedbacks
