import os
import json
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.schema import Document
from loguru import logger
from dotenv import load_dotenv
load_dotenv()

class Embedder:
    def __init__(self, output_base_dir):
        self.output_base_dir = output_base_dir
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.langchain_api_key = os.getenv("LANGCHAIN_API_KEY")
        
        if not self.openai_api_key or not self.langchain_api_key:
            raise ValueError("API keys are missing. Please set OPENAI_API_KEY and LANGCHAIN_API_KEY.")
        
        # Initialize the OpenAI Embeddings with the provided API key
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        
        self.vectorstore = None

    def load_processed_json(self, file_path):
        """Load processed JSON file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def convert_to_documents(self, data, source):
        """Convert JSON data into LangChain Document format with source tracking."""
        documents = []
        for url, content in data.items():
            page_content = (
                f"Title: {content.get('title', '')}\n"
                f"Headers: {', '.join(content.get('headers', []))}\n"
                f"Paragraphs: {' '.join(content.get('paragraphs', []))}\n"
                f"Lists: {' '.join(content.get('lists', []))}\n"
                f"Tables: {content.get('tables', [])}\n"
                f"Code Blocks: {content.get('code_blocks', [])}"
            )
            # Add source information to metadata
            metadata = {
                "url": url,
                "source": source  
            }
            documents.append(Document(page_content=page_content, metadata=metadata))
        return documents

    def create_embeddings(self, input_files):
        """Generate embeddings and save them to a single vector store."""
        all_documents = []
        
        # First, collect all documents from all files
        for file_path in input_files:
            logger.info(f"Processing {file_path} for embeddings...")
            # Load and validate the JSON data
            data = self.load_processed_json(file_path)

            # Get source identifier from the file path
            source = os.path.basename(os.path.dirname(file_path))
            
            # Convert JSON data to LangChain Document objects with source tracking
            documents = self.convert_to_documents(data, source)
            all_documents.extend(documents)

        # Create the vector store directory if it doesn't exist
        os.makedirs(self.output_base_dir, exist_ok=True)

        # Create or update the vector store with all documents
        if self.vectorstore is None:
            # Initialize vector store if it doesn't exist
            self.vectorstore = Chroma.from_documents(
                documents=all_documents,
                embedding=self.embeddings,
                persist_directory=self.output_base_dir
            )
        else:
            # Add new documents to existing vector store
            self.vectorstore.add_documents(all_documents)

        logger.info(f"All embeddings saved to {self.output_base_dir}")

