import os
import openai
import numpy as np
from loguru import logger
from pymongo import MongoClient
from typing import Dict, List, Optional
from functools import lru_cache
from dotenv import load_dotenv
# from services.log_manager import log_manager

load_dotenv()

class MongoService:
    def __init__(self):
        logger.info("Initializing MongoService...")
        try:
            mongo_uri = os.getenv("MONGO_URI")
            db_name = os.getenv("MONGO_DB_NAME")
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            
            # Collections
            self.announcements_collection = self.db[os.getenv("ANNOUNCEMENTS_COLLECTION")]
            self.embeddings_collection = self.db[os.getenv("ANNOUNCEMENTS_COLLECTION")]

            openai.api_key = os.getenv("OPENAI_API_KEY")
            logger.info("MongoService initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing MongoService: {str(e)}")
            raise

    def preprocess_text(self, text: str) -> str:
        logger.debug(f"Preprocessing text: {text}")
        return ' '.join(text.split()).strip()

    def normalize_embedding(self, embedding: List[float]) -> List[float]:
        norm = np.linalg.norm(embedding)
        normalized = (embedding / norm).tolist() if norm > 0 else embedding
        logger.debug(f"Normalized embedding: {normalized[:5]}... (truncated)")
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

            logger.debug(f"Generated embedding: {embedding[:5]}... (truncated)")
            return self.normalize_embedding(embedding)
        except Exception as e:
            logger.error(f"Error generating embedding using OpenAI API: {str(e)}")
            raise

    def upsert_announcement(self, metadata: Dict) -> bool:
        logger.info(f"Upserting announcement with metadata: {metadata}")
        try:
            content = metadata.get("content", "").strip()
            if not content:
                logger.error("No content found in metadata. Aborting upsert.")
                return False

            processed_content = self.preprocess_text(content)
            embedding = self.generate_embedding(processed_content)
            announcement_id = f"{metadata['channel']}_{metadata['timestamp']}"

            # Upsert into announcements collection
            announcement_document = {
                "_id": announcement_id,
                "embedding": embedding,
                "metadata": metadata
            }
            self.announcements_collection.replace_one(
                {"_id": announcement_id}, announcement_document, upsert=True
            )
            logger.info(f"Inserted/updated announcement with ID: {announcement_id}")

            # Upsert into embeddings collection
            embedding_document = {
                "_id": announcement_id,
                "embedding": embedding,
                "metadata": metadata
            }
            self.embeddings_collection.replace_one(
                {"_id": announcement_id}, embedding_document, upsert=True
            )
            logger.info(f"Inserted/updated embedding with ID: {announcement_id}")
            return True
        except Exception as e:
            logger.error(f"Error upserting announcement: {str(e)}")
            return False

    def search_announcements(self, query: str) -> List[Dict]:
        logger.info(f"Searching for announcements relevant to query: {query}")
        try:
            # Preprocess the query and generate its embedding
            processed_query = self.preprocess_text(query)
            query_embedding = self.generate_embedding(processed_query)
            logger.debug(f"Query embedding: {query_embedding}")

            logger.debug("Performing vector similarity search in MongoDB using knnBeta...")
            
            # Use the aggregate pipeline with knnBeta for vector search
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
            logger.debug("=====================================================\n")
            logger.debug(self.embeddings_collection)
            results = list(self.embeddings_collection.aggregate(pipeline))
            logger.debug(f"Search results: {results}")
            contexts = []
            for result in results:
                logger.debug(f"Processing search result with ID: {result['_id']}")

                # Fetch the announcement metadata using the ID
                announcement = self.announcements_collection.find_one({"_id": result["_id"]})
                print("===========================================\n")
                print(announcement.keys())
                if announcement:
                    contexts.append({
                        "content": announcement["metadata"]["content"],
                        "channel": announcement["metadata"]["channel"],
                        "timestamp": announcement["metadata"]["timestamp"],
                        "similarity": result["score"]  # Use the similarity score from knnBeta
                    })

            logger.info(f"Found {len(contexts)} relevant announcements.")
            return contexts
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []


    def _create_prompt(self, query: str, contexts: List[Dict]) -> str:
        logger.info(f"Creating prompt for query: {query}")
        prompt = f"User Query: {query}\n\nRelevant Announcements:\n\n"
        
        if not contexts:
            prompt += "No relevant announcements found.\n"
        else:
            for idx, context in enumerate(contexts, 1):
                prompt += f"Announcement {idx}:\n{context['content']}\n\n"

        prompt += "\nBased on these announcements, please provide a relevant response to the user's query. "
        prompt += "Include specific details when available. "
        prompt += "If the announcements don't contain relevant information, please indicate that."
        
        logger.debug(f"Generated prompt: {prompt[:100]}... (truncated)")
        return prompt

    def generate_response_from_mongo(self, user_query: str) -> Dict:
        try:
            # Search for relevant announcements
            contexts = self.search_announcements(user_query)

            # Define the system prompt
            system_prompt = """You are a helpful assistant that provides information about announcements. 
            Your task is to:
            1. Answer questions about announcements, events, and updates
            2. If a query is about dates or upcoming events, focus on temporal aspects
            3. Provide specific details from the announcements when available
            4. If multiple announcements are relevant, combine the information coherently
            5. If no announcements match the query, clearly state that
            
            Always maintain a helpful and informative tone."""

            # Create the user prompt
            user_prompt = self._create_prompt(user_query, contexts)
            api_key1=os.getenv("OPENAI_API_KEY")
            client = openai.Client(api_key=api_key1)
            # Generate response using the new OpenAI API
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            # Extract the response content
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

