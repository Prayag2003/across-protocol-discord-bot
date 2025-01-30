import os
import json
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document
from loguru import logger
from dotenv import load_dotenv
load_dotenv()

class AnnouncementEmbedder:
    def __init__(self, output_base_dir):
        self.output_base_dir = output_base_dir
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is missing. Please set it in the environment variables.")

        # Initialize the OpenAI Embeddings with the provided API key
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)

        # Ensure the output directory exists
        os.makedirs(self.output_base_dir, exist_ok=True)

        # Initialize Chroma client
        self.vectorstore = Chroma(
            persist_directory=self.output_base_dir,
            embedding_function=self.embeddings
        )
        logger.info(f"Vector store initialized at {self.output_base_dir}")

    def format_announcement(self, content, channel_name, author_name, timestamp, url):
        """Format announcement metadata into a single document."""
        formatted_content = (
            f"Content: {content}\n"
            f"Channel: {channel_name}\n"
            f"Author: {author_name}\n"
            f"Timestamp: {timestamp}\n"
            f"URL: {url}"
        )
        metadata = {
            "channel": channel_name,
            "author": author_name,
            "timestamp": timestamp,
            "url": url
        }
        return Document(page_content=formatted_content, metadata=metadata)

    def save_to_vectorstore(self, document):
        """Save a single document to the vector store."""
        try:
            # Add document to the vector store
            ids = [str(hash(document.page_content))]  # Generate a unique ID for the document
            self.vectorstore.add_documents(
                documents=[document],
                ids=ids
            )
            
            logger.info(f"Document successfully saved to vector store at {self.output_base_dir}")
            return True
        except Exception as e:
            logger.error(f"Error saving document to vector store: {e}")
            return False

    def search_similar(self, query, k=5):
        """Search for similar announcements in the vector store."""
        try:
            results = self.vectorstore.similarity_search(query, k=k)
            return results
        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            return []