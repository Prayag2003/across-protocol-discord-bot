import os
import json
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
    _instance = None
    _is_initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not MongoService._is_initialized:
            try:
                mongo_uri = os.getenv("MONGO_URI")
                db_name = os.getenv("MONGO_DB_NAME")
                self.client = MongoClient(mongo_uri)
                self.db = self.client[db_name]
                
                # Collections
                self.announcements_collection = self.db[os.getenv("ANNOUNCEMENTS_COLLECTION")]
                openai.api_key = os.getenv("OPENAI_API_KEY")
                
                # Check and create vector search index only once
                self._create_vector_search_index()
                
                MongoService._is_initialized = True
                logger.info("MongoService initialized successfully")

            except Exception as e:
                logger.error(f"Error initializing MongoService: {str(e)}")
                raise

    def _create_vector_search_index(self):
        """Create vector search index if it doesn't exist"""
        try:
            existing_indexes = list(self.announcements_collection.list_indexes())
            index_names = [idx.get('name') for idx in existing_indexes]
            
            if "vector_index" not in index_names:
                logger.info("Creating vector search index...")
                
                index_model = {
                    "definition": {
                        "mappings": {
                            "dynamic": True,
                            "fields": {
                                "embedding": {
                                    "dimensions": 1536,
                                    "similarity": "cosine",
                                    "type": "knnVector"
                                }
                            }
                        }
                    },
                    "name": "vector_index"
                }
                
                self.announcements_collection.create_search_index(
                    model=index_model
                )
                logger.info("Vector search index created successfully")
            else:
                logger.info("Vector search index already exists")
            
            logger.info(f"Current indexes: {', '.join(index_names)}")
            
        except Exception as e:
            logger.error(f"Error creating vector search index: {str(e)}, full error: {e.details if hasattr(e, 'details') else str(e)}")
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
        logger.info(f"Searching relevant announcements | query: {query}")
        try:
            processed_query = self.preprocess_text(query)
            query_embedding = self.generate_embedding(processed_query)
            
            # Debug log for query and embedding
            logger.debug(f"Processed query: {processed_query}")
            logger.debug(f"Generated embedding shape: {len(query_embedding)}")
            
            # Log collection stats
            doc_count = self.announcements_collection.count_documents({})
            logger.info(f"Collection has {doc_count} documents")
            
            # Check if vector index exists
            # indexes = self.announcements_collection.list_indexes()
            # print("Indexes: ", indexes)
            # vector_index_exists = any("vector_index" in idx.get("name", "") for idx in indexes)
            # logger.info(f"Vector index exists: {vector_index_exists}")

            vector_pipeline = [
                {
                    "$vectorSearch": {
                        "index": "vector_index",
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": 100, 
                        "limit": 5
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "metadata": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]

            logger.info("Executing vector search pipeline...")
            try:
                results = list(self.announcements_collection.aggregate(vector_pipeline))
                logger.info(f"Found {len(results)} results from vector search")
                
                if not results:
                    logger.warning("Vector search returned no results, checking collection sample...")

                    sample_doc = self.announcements_collection.find_one()
                    logger.debug(f"Sample document structure: {json.dumps(sample_doc, indent=2)}")
                    
                    
                    logger.info("Falling back to text search...")
                    text_pipeline = [
                        {
                            "$match": {
                                "$text": {"$search": processed_query}
                            }
                        },
                        {
                            "$project": {
                                "_id": 1,
                                "metadata": 1,
                                "score": {"$meta": "textScore"}
                            }
                        },
                        {"$sort": {"score": -1}},
                        {"$limit": 5}
                    ]
                    results = list(self.announcements_collection.aggregate(text_pipeline))
                    logger.info(f"Text search found {len(results)} results")

            except Exception as e:
                logger.error(f"Search failed: {str(e)}", exc_info=True)
                # Log the MongoDB server version and topology
                server_info = self.announcements_collection.database.client.server_info()
                logger.debug(f"MongoDB server version: {server_info.get('version')}")
                return []

            # Enhanced result logging
            for idx, result in enumerate(results):
                logger.info(f"Document {idx + 1}:")
                logger.info(f"ID: {result.get('_id')}")
                logger.info(f"Timestamp: {result['metadata'].get('timestamp', 'N/A')}")
                logger.info(f"Channel: {result['metadata'].get('channel', 'N/A')}")
                logger.info(f"Content preview: {result['metadata'].get('content', '')[:100]}...")
                logger.info(f"Search score: {result.get('score', 0)}")
                logger.info("-" * 50)

            # Process results
            contexts = []
            for result in results:
                try:
                    metadata = result.get('metadata', {})
                    context = {
                        "content": metadata.get('content', ''),
                        "channel": metadata.get('channel', ''),
                        "timestamp": metadata.get('timestamp', ''),
                        "similarity": result.get('score', 0)
                    }
                    contexts.append(context)
                except Exception as e:
                    logger.error(f"Error processing result: {str(e)}", exc_info=True)

            # Final sort by timestamp
            contexts.sort(
                key=lambda x: self.parse_timestamp(x["timestamp"]),
                reverse=True
            )

            logger.info(f"Final processed contexts count: {len(contexts)}")
            
            # Log processed contexts for debugging
            if contexts:
                logger.info("Sample of found contexts:")
                for ctx in contexts[:2]:
                    logger.info(f"- Content preview: {ctx['content'][:100]}")
                    logger.info(f"- Timestamp: {ctx['timestamp']}")
                    logger.info(f"- Channel: {ctx['channel']}")
                    logger.info(f"- Similarity score: {ctx['similarity']}")
            else:
                logger.warning("No contexts found after processing")
                # Log the query parameters for debugging
                logger.debug(f"Search parameters:")
                logger.debug(f"- Original query: {query}")
                logger.debug(f"- Processed query: {processed_query}")
                logger.debug(f"- Embedding dimensions: {len(query_embedding)}")

            return contexts

        except Exception as e:
            logger.error(f"Critical error during search: {str(e)}", exc_info=True)
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
        
        logger.debug(f"Generated prompt: {prompt}")
        return prompt

    def generate_response_from_mongo(self, user_query: str) -> Dict:
        try:
            contexts = self.search_announcements(user_query)

            system_prompt = """You are a helpful discord bot assistant that provides information about announcements. 
            Your task is to:
            1. Always prefer latest announcements as per time stamp to give accurate results.Take this very seriously.
            2. The results must not be ambiguous.
            3. Answer questions about announcements, events, updates and news.
            4. Always prioritize the most recent information, as it represents the current state.
            5. When discussing status updates or changes, explicitly mention the latest known state.
            6. Include relevant timestamps to provide context about when information was announced.
            7. If there are conflicting announcements, explain the timeline and current status.
            8. If no announcements match the query, clearly state that.
            
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
                temperature=0.2,
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