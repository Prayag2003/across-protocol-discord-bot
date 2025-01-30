import os
import json
import openai
from loguru import logger
from typing import List, Dict, Any, Tuple
from langchain_openai import OpenAIEmbeddings  # Updated import
from langchain_chroma import Chroma
from langchain.schema import Document
from dotenv import load_dotenv
from inference.template.prompt_template_v2 import generate_prompt_template
from inference.template.announce_prompt_template import generate_announce_prompt_template

load_dotenv()

class InferenceEngine:
    def __init__(self, vectorstore_path: str):

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.error("OPENAI_API_KEY is missing in environment variables")
            raise ValueError("OPENAI_API_KEY is missing in environment variables")
        
        openai.api_key = self.openai_api_key
        self.vectorstore_path = vectorstore_path
        self.embeddings = OpenAIEmbeddings(openai_api_key=self.openai_api_key)
        self.vectorstore = None

        logger.info("InferenceEngine initialized successfully")

    def initialize_vectorstore(self):
        """Initialize or load the vector store."""
        if self.vectorstore is None:
            logger.info("Initializing vector store")
            self.vectorstore = Chroma(
                persist_directory=self.vectorstore_path,
                embedding_function=self.embeddings
            )
            logger.info("Vector store initialized")
        return self.vectorstore

    def query_vector_store(self, query_text: str, top_k: int = 3) -> List[Document]:
        """Query the vector store and return relevant documents."""
        logger.info(f"Querying vector store with text: {query_text} and top_k: {top_k}")
        vectorstore = self.initialize_vectorstore()
        retriever = vectorstore.as_retriever(search_kwargs={"k": top_k})
        results = retriever.invoke(query_text)
        logger.info(f"Retrieved {len(results)} documents from vector store")
        return results

    def generate_openai_response(self, prompt_template: List[Dict[str, str]], max_tokens: int = 800, temperature: float = 0.15) -> str:
        """Generate a response from OpenAI based on the prompt template."""
        try:
            logger.info("Generating OpenAI response")
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=prompt_template,
                max_tokens=max_tokens,
                temperature=temperature
            )
            logger.info("OpenAI response generated successfully")
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            return None

    def format_references(self, results: List[Document]) -> str:
        """Format reference URLs from the retrieved documents."""
        logger.info("Formatting references from retrieved documents")
        references = set()  
        for result in results:
            url = result.metadata.get('url')
            if url:
                references.add(f"Source: {url}")
        formatted_references = "\n".join(references)
        logger.info("References formatted successfully")
        return formatted_references

    def process_query(
        self, query_text: str, username: str, role: str = "user", detail_level: str = "detailed", top_k: int = 1,debug: bool = False ) -> Dict[str, Any]:
        """
        Process a query and return the response with references and debug information.
        """
        logger.info(f"Processing query: {query_text} for user: {username}")

        # Get relevant documents
        results = self.query_vector_store(query_text, top_k)
        logger.info(f"Retrieved {len(results)} documents from vector store")
        logger.info(f"Results: {results}")  

        # Build context from results
        context = "\n".join([result.page_content for result in results])
        
        # Generate prompt template
        prompt_template = generate_prompt_template(
            context,
            query_text,
            role,
            detail_level,
            references=results
        )

        # Generate response
        response = self.generate_openai_response(prompt_template)
        logger.info(f"Type of response: {type(response)}")  
        logger.info(f"Response generated: {response[:50]}...")
        
        # Format references
        formatted_references = self.format_references(results)
        logger.info(f"Formatted references: {formatted_references}")
        logger.info("Query processed successfully")
        return response 