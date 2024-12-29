import os
import openai
import numpy as np
from loguru import logger
from pymongo import MongoClient
from typing import Dict, List, Optional
from functools import lru_cache
from dotenv import load_dotenv
from datetime import datetime
from dateutil.parser import parse as parse_iso

load_dotenv()

class MongoService:
    def __init__(self):
        try:
            mongo_uri = os.getenv("MONGO_URI")
            db_name = os.getenv("MONGO_DB_NAME")
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            
            # Collections
            self.announcements_collection = self.db[os.getenv("ANNOUNCEMENTS_COLLECTION")]
            openai.api_key = os.getenv("OPENAI_API_KEY")
            
        except Exception as e:
            logger.error(f"Error initializing MongoService: {str(e)}")
            raise

    def preprocess_text(self, text: str) -> str:
        logger.info(f"Preprocessing text")
        return ' '.join(text.split()).strip()
    
    def normalize_embedding(self, embedding: List[float]) -> List[float]:
        norm = np.linalg.norm(embedding)
        normalized = (embedding / norm).tolist() if norm > 0 else embedding
        return normalized

    @lru_cache(maxsize=1000)
    def generate_embedding(self, text: str) -> List[float]:
        logger.info(f"Generating embedding for text: {text}")
        try:
            response = openai.embeddings.create(
                input=text,
                model="text-embedding-ada-002"
            )
            embedding = response.data[0].embedding
            return self.normalize_embedding(embedding)
        except Exception as e:
            logger.error(f"Error generating embedding using OpenAI API: {str(e)}")
            raise

    
    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parses timestamp string into datetime object."""
        try:
            # Parse ISO 8601 format
            return parse_iso(timestamp_str)
        except Exception as e:
            logger.error(f"Error parsing timestamp {timestamp_str}: {str(e)}")
            return datetime.min


    def upsert_announcement(self, metadata: Dict) -> bool:
        logger.info(f"Upserting announcement")
        try:
            content = metadata.get("content", "").strip()
            if not content:
                logger.error("No content found in metadata. Aborting upsert.")
                return False

            processed_content = self.preprocess_text(content)
            embedding = self.generate_embedding(processed_content)
            announcement_id = f"{metadata['channel']}_{metadata['timestamp']}"

            announcement_document = {
                "_id": announcement_id,
                "embedding": embedding,
                "metadata": metadata
            }
            self.announcements_collection.replace_one(
                {"_id": announcement_id}, announcement_document, upsert=True
            )
            logger.info(f"Inserted/updated announcement with ID: {announcement_id}")

            return True
        except Exception as e:
            logger.error(f"Error upserting announcement: {str(e)}")
            return False

    def search_announcements(self, query: str) -> List[Dict]:
        logger.info(f"Searching for announcements relevant to query: {query}")
        try:
            processed_query = self.preprocess_text(query)
            query_embedding = self.generate_embedding(processed_query)

            logger.info("Performing vector similarity search in MongoDB using knnBeta...")
            
            pipeline = [
                {
                    "$search": {
                        "knnBeta": {
                            "vector": query_embedding,
                            "path": "embedding",
                            "k": 5
                        }
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "embedding": 1,
                        "score": {"$meta": "searchScore"}
                    }
                }
            ]

            results = list(self.announcements_collection.aggregate(pipeline))

            contexts = []
            for result in results:
                logger.info(f"Processing result | ID:{result['_id']}")
                announcement = self.announcements_collection.find_one({"_id": result["_id"]})
                if announcement:
                    contexts.append({
                        "content": announcement["metadata"]["content"],
                        "channel": announcement["metadata"]["channel"],
                        "timestamp": announcement["metadata"]["timestamp"],
                        "similarity": result["score"]
                    })
            
            # Sort contexts by timestamp in descending order (most recent first)
            contexts.sort(
                key=lambda x: self.parse_timestamp(x["timestamp"]),
                reverse=True
            )

            logger.info(f"Found {len(contexts)} relevant announcements, sorted by timestamp.")
            return contexts
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []


    def _create_prompt(self, query: str, contexts: List[Dict]) -> str:
        prompt = f"User Query: {query}\n\nRelevant Announcements (sorted by most recent first):\n\n"
        
        if not contexts:
            prompt += "No relevant announcements found.\n"
        else:
            for idx, context in enumerate(contexts, 1):
                prompt += (
                    f"[Announcement {idx} - {context['timestamp']}]\n"
                    f"{context['content']}\n\n"
                )

        prompt += (
            "\nBased on these announcements, please provide a relevant response to the user's query. "
            "Important notes:\n"
            "1. Recent announcements carry more weight and may override older information.\n"
            "2. If conflicting statements exist, prioritize the most recent one.\n"
            "3. Provide specific details and timestamps when possible to offer clear context.\n"
            "4. If the announcements lack relevant details, explicitly mention this.\n"
        )
        
        logger.debug(f"Generated prompt: {prompt[:100]}... (truncated)")
        return prompt

    def generate_response_from_mongo(self, user_query: str) -> Dict:
        try:
            contexts = self.search_announcements(user_query)

            system_prompt = """You are a helpful discord bot assistant that provides information about announcements. 
            Your task is to:
            1. Answer questions about announcements, events, and updates.
            2. Always prioritize the most recent information, as it represents the current state
            3. When discussing status updates or changes, explicitly mention the latest known state
            4. Include relevant timestamps to provide context about when information was announced
            5. If there are conflicting announcements, explain the timeline and current status
            6. If no announcements match the query, clearly state that
            
            Always maintain a helpful and informative tone while ensuring users understand the current state of affairs."""

            user_prompt = self._create_prompt(user_query, contexts)
            api_key1 = os.getenv("OPENAI_API_KEY")
            client = openai.Client(api_key=api_key1)
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            response_content = response.choices[0].message.content
            
            return {
                "response": response_content,
                "contexts": contexts,
                "query": user_query
            }
        except Exception as e:
            return {
                "response": "Sorry, I encountered an error while searching for announcements.",
                "error": str(e)
            }