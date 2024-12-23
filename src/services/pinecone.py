import os
import json
from loguru import logger
from datetime import datetime
from typing import Dict, List, Optional

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

class PineconeService:
    def __init__(self, pinecone_api_key: str, index_name: str, openai_api_key: str):

        self.pinecone_client = Pinecone(api_key=pinecone_api_key)
        if index_name not in self.pinecone_client.list_indexes().names():
            self.pinecone_client.create_index(
                name=index_name,
                dimension=1536,  
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )

        while not self.pinecone_client.describe_index(index_name).status["ready"]:
            time.sleep(1)

        self.index = self.pinecone_client.Index(index_name)        
        self.client = OpenAI(api_key=openai_api_key)

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for the given text using OpenAI's embedding model."""
        try:
            response = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def generate_response_from_pinecone(self, user_query: str) -> Dict:
        """
        Search Pinecone index and generate a response based on the user query.
        
        Args:
            user_query (str): The user's query string.

        Returns:
            Dict: A dictionary containing the response and relevant announcements.
        """
        try:
            # Generate embedding for the user query
            query_embedding = self.generate_embedding(user_query)
            
            # Query the Pinecone index
            search_response = self.index.query(
                vector=query_embedding,
                top_k=5,
                include_metadata=True
            )
            
            # Parse the search results
            contexts = []
            print("Search responses: \n", search_response.matches)
            for match in search_response.matches:
                if match.score < 0.7:  
                    continue

                # Ensure metadata is a dictionary
                if not isinstance(match.metadata, dict):
                    logger.error(f"Metadata is not a dictionary: {match.metadata}")
                    continue
                
                contexts.append({
                    "content": match.metadata.get("content"),
                    "channel": match.metadata.get("channel"),
                    "author": match.metadata.get("author"),
                    "timestamp": match.metadata.get("timestamp"),
                    "url": match.metadata.get("url"),
                    "similarity": match.score
                })

            logger.info("Contexts: ", contexts)
            # Generate a prompt for the OpenAI model
            prompt = self._create_prompt(user_query, contexts)
            logger.info(f"Generated prompt: {prompt}")
            
            # Generate response using OpenAI's GPT model
            completion = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": """You are a helpful assistant that provides information about Discord announcements. 
                    Your responses should be clear, concise, and directly related to the user's query. 
                    If multiple announcements are relevant, summarize them chronologically."""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            response = completion.choices[0].message.content
            logger.info(f"Generated response: {response}")
            
            return {
                "response": response,
                "announcements": contexts,
                "query": user_query
            }
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return {
                "response": "Sorry, I encountered an error while searching for announcements.",
                "error": str(e)
            }

    def _create_prompt(self, query: str, contexts: List[Dict]) -> str:
        """Create a prompt for OpenAI based on the query and retrieved contexts."""
        prompt = f"User Query: {query}\n\nRelevant Announcements:\n"
        
        for idx, context in enumerate(contexts, 1):
            prompt += f"\n{idx}. Content: {context['content']}"
            prompt += f"\nChannel: {context['channel']}"
            prompt += f"\nAuthor: {context['author']}"
            prompt += f"\nTimestamp: {context['timestamp']}"
            prompt += f"\nURL: {context['url']}\n"
        
        prompt += "\nPlease provide a response that addresses the user's query based on these announcements. " \
                 "If the announcements don't contain relevant information, please indicate that."
        
        return prompt

    def upsert_announcement(self, metadata: Dict) -> bool:
        try:
            # Generate embedding for the announcement content
            embedding = self.generate_embedding(metadata["content"])
            
            # Create a unique ID for the announcement
            announcement_id = f"{metadata['channel']}_{metadata['timestamp']}"
            
            self.index.upsert(
                vectors=[(announcement_id, embedding, metadata)]
            )            
            return True

        except Exception as e:
            logger.error(f"Error upserting announcement: {str(e)}")
            return False