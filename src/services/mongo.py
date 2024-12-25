import os
import openai
import numpy as np
from loguru import logger
from pymongo import MongoClient
from typing import Dict, List, Optional
from functools import lru_cache
from dotenv import load_dotenv

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
            self.embeddings_collection = self.db[os.getenv("EMBEDDINGS_COLLECTION")]

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
            # return embedding
        except Exception as e:
            logger.error(f"Error generating embedding using openai.embeddings.create: {str(e)}")
            try:
                # Alternative method for generating embedding
                response = openai.embeddings.create(
                    input=text,
                    model="text-embedding-ada-002"
                )
                embedding = response.data[0].embedding
                logger.debug(f"Fallback generated embedding: {embedding[:5]}... (truncated)")
                return self.normalize_embedding(embedding)
                # return embedding
            except Exception as fallback_e:
                logger.error(f"Error during fallback embedding generation: {str(fallback_e)}")
                raise Exception(f"Both methods failed to generate embedding: {str(fallback_e)}")

    def upsert_announcement(self, metadata: Dict) -> bool:
        logger.info(f"Upserting announcement with metadata: {metadata}")
        try:
            content = metadata.get("content", "").strip()
            if not content:
                logger.error("No content found in metadata. Aborting upsert.")
                return False

            processed_content = self.preprocess_text(content)
            
            print(processed_content)
            embedding = self.generate_embedding(processed_content)
            announcement_id = f"{metadata['channel']}_{metadata['timestamp']}"

            # Upsert into announcements collection
            announcement_document = {
                "_id": announcement_id,
                "embedding":embedding,
                "metadata": metadata
            }
            self.announcements_collection.replace_one(
                {"_id": announcement_id}, announcement_document, upsert=True
            )
            logger.info(f"Inserted/updated announcement with ID: {announcement_id}")

            # Upsert into embeddings collection
            embedding_document = {
                "_id": announcement_id,
                "embedding": embedding
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
            processed_query = self.preprocess_text(query)
            query_embedding = self.generate_embedding(processed_query)

            logger.debug("Performing vector similarity search in MongoDB...")
            results = self.embeddings_collection.find({
                "embedding": {"$near": {"$vector": query_embedding}}
            }).limit(5)

            contexts = []
            for result in results:
                logger.debug(f"Processing search result with ID: {result['_id']}")
                
                # Compute similarity score using cosine similarity
                stored_embedding = np.array(result["embedding"])
                query_embedding_np = np.array(query_embedding)
                similarity_score = np.dot(stored_embedding, query_embedding_np) / (
                    np.linalg.norm(stored_embedding) * np.linalg.norm(query_embedding_np)
                )
                
                logger.debug(f"Similarity score for ID {result['_id']}: {similarity_score:.4f}")

                announcement = self.announcements_collection.find_one({"_id": result["_id"]})
                if announcement:
                    contexts.append({
                        "content": announcement["metadata"]["content"],
                        "channel": announcement["metadata"]["channel"],
                        "timestamp": announcement["metadata"]["timestamp"],
                        "similarity": similarity_score
                    })
            
            # Print similarity scores for debugging
            print("contexts: "+contexts)
            for idx, context in enumerate(contexts):
                logger.info(
                    f"Result {idx + 1}: ID={context.get('id', 'N/A')} | Similarity={context['similarity']:.4f}"
                )

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
        logger.info(f"Generating response for user query: {user_query}")
        try:
            contexts = self.search_announcements(user_query)
            
            system_prompt = """You are a helpful assistant that provides information about announcements. 
            Your task is to:
            1. Answer questions about announcements, events, and updates
            2. If a query is about dates or upcoming events, focus on temporal aspects
            3. Provide specific details from the announcements when available
            4. If multiple announcements are relevant, combine the information coherently
            5. If no announcements match the query, clearly state that
            
            Always maintain a helpful and informative tone."""

            user_prompt = self._create_prompt(user_query, contexts)

            logger.info("Requesting OpenAI for response generation...")
            completion = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            response = completion.choices[0].message["content"]
            logger.info("Response generated successfully.")
            
            return {
                "response": response,
                "contexts": contexts,  # Includes similarity scores
                "query": user_query
            }
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": "Sorry, I encountered an error while searching for announcements.",
                "error": str(e)
            }

            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": "Sorry, I encountered an error while searching for announcements.",
                "error": str(e)
            }
   