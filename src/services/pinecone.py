import os
import json
import time
from loguru import logger
from datetime import datetime, timedelta
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

    def preprocess_text(self, text: str) -> str:
        """Basic text preprocessing to improve embedding quality."""
        # Remove extra whitespace and normalize
        return ' '.join(text.split()).strip()

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
        Focuses on semantic relevance rather than exact matching.
        """
        try:
            # Preprocess and generate embedding for user query
            processed_query = self.preprocess_text(user_query)
            query_embedding = self.generate_embedding(processed_query)
            
            search_response = self.index.query(
                vector=query_embedding,
                top_k=3,  
                include_metadata=True
            )
            
            # Process search results
            contexts = []
            for match in search_response.matches:
                if match.score < 0.6:  
                    continue
                
                if isinstance(match.metadata, dict):
                    contexts.append({
                        "content": match.metadata.get("content", ""),
                        "channel": match.metadata.get("channel", ""),
                        "timestamp": match.metadata.get("timestamp", ""),
                        "similarity": match.score
                    })

            print("Search responses:\n", search_response)
            print("contexts:", contexts)

            # Generate prompt for OpenAI
            system_prompt = """You are a helpful assistant that provides information about announcements. 
            Your task is to:
            1. Answer questions about announcements, events, and updates
            2. If a query is about dates or upcoming events, focus on temporal aspects
            3. Provide specific details from the announcements when available
            4. If multiple announcements are relevant, combine the information coherently
            5. If no announcements match the query, clearly state that
            
            Always maintain a helpful and informative tone."""

            user_prompt = self._create_prompt(user_query, contexts)

            print("Prompt: \n", user_prompt)

            # Generate response using OpenAI
            completion = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "response": completion.choices[0].message.content,
                "contexts": contexts,
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
        prompt = f"User Query: {query}\n\nRelevant Announcements:\n\n"
        
        if not contexts:
            prompt += "No relevant announcements found.\n"
        else:
            for idx, context in enumerate(contexts, 1):
                prompt += f"Announcement {idx}:\n{context['content']}\n\n"

        prompt += "\nBased on these announcements, please provide a relevant response to the user's query. "
        prompt += "Include specific details when available. "
        prompt += "If the announcements don't contain relevant information, please indicate that."
        
        return prompt


    def upsert_announcement(self, metadata: Dict) -> bool:
        """Store announcement in Pinecone with its embedding."""
        try:
            # Preprocess the content
            content = metadata.get("content", "")
            processed_content = self.preprocess_text(content)
            
            # Generate embedding
            embedding = self.generate_embedding(processed_content)
            
            # Create unique ID
            announcement_id = f"{metadata['channel']}_{metadata['timestamp']}"
            
            # Store in Pinecone
            self.index.upsert(
                vectors=[(announcement_id, embedding, metadata)]
            )            
            return True

        except Exception as e:
            logger.error(f"Error upserting announcement: {str(e)}")
            return False