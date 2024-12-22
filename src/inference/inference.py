import os
import re
import json
import numpy as np
from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv
from pymongo import MongoClient 
from sklearn.metrics.pairwise import cosine_similarity
from inference.logger import log_query_and_response
from inference.template.prompt_template import generate_prompt_template

load_dotenv()

def load_embeddings(file_path):
    """Load embeddings from file, with MongoDB fallback."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Failed to load embeddings from file: {str(e)}")
        logger.info("Attempting to load embeddings from MongoDB as fallback...")
        try:
            client = MongoClient(os.getenv('MONGO_URI'))
            db = client[os.getenv('MONGO_DB_NAME')]
            collection = db[os.getenv('EMBEDDINGS_COLLECTION')]

            # Load embeddings from MongoDB
            embeddings_list = list(collection.find({}, {'_id': 0})) 
            logger.info("Successfully loaded embeddings from MongoDB.")
            return embeddings_list

        except Exception as db_e:
            raise Exception(f"Error loading embeddings from MongoDB: {str(db_e)}")

def generate_embedding_for_query(client, text):
    """Generate embedding with error handling"""
    try:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Error generating embedding: {str(e)}")

def compute_similarity(query_embedding, embeddings_list, query):
    """Enhanced similarity computation"""
    similarities = []
    logger.info("Computing similarities for the query embedding...")
    query_terms = query.lower().split()

    for entry in embeddings_list:
        try:
            url = entry['url']
            embedding = entry['embedding']
            content = entry.get('content', '') 
            
            embedding_array = np.array(embedding)
            query_embedding_array = np.array(query_embedding)
            similarity = cosine_similarity([query_embedding_array], [embedding_array])[0][0]
            similarities.append((url, similarity, content))  
                
        except Exception as e:
            logger.error(f"Error processing document {entry.get('url', 'unknown')}: {str(e)}")
            continue

    return similarities

def find_most_similar_documents(query_embedding, embeddings_list, query, top_n=3):
    """Find most similar documents with improved filtering"""
    logger.info(f"Found top {top_n} similar documents...")
    similarities = compute_similarity(query_embedding, embeddings_list, query)
    
    filtered_similarities = [
        (url, sim, content) for url, sim, content in similarities 
        if sim > 0.3  
    ]
    
    sorted_similarities = sorted(filtered_similarities, key=lambda x: x[1], reverse=True)
    
    logger.info("Similarity scores:")
    for url, sim, _ in sorted_similarities[:top_n]:
        logger.info(f"{url}: {sim:.3f}")
    
    return sorted_similarities[:top_n]


def extract_references(context):
    """Extract unique references from the context."""
    references = []
    # Use regex to find all URLs in markdown link format
    url_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    matches = re.finditer(url_pattern, context)
    
    # Create a set of tuples (title, url) to ensure uniqueness
    unique_refs = set()
    for match in matches:
        title = match.group(1)
        url = match.group(2)
        unique_refs.add((title, url))
    
    # Convert set back to list and format references
    references = [f"- [{title}]({url})" for title, url in unique_refs]
    return references


def extract_references(context):
    """Extract unique references from the context."""
    references = []
    url_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    matches = re.finditer(url_pattern, context)
    
    unique_refs = set()
    for match in matches:
        title = match.group(1)
        url = match.group(2)
        unique_refs.add((title, url))
    
    references = [f"- [{title}]({url})" for title, url in unique_refs]
    return references

def format_response_with_references(response_text, references):
    """Format the final response with references section."""
    if not references:
        return response_text
        
    formatted_response = response_text.strip()
    
    # Only add references section if it doesn't already exist
    if "## References" not in formatted_response and references:
        formatted_response += "\n\n## References\n"
        formatted_response += "\n".join(references)
    
    return formatted_response

    
def generate_response_with_context(user_query: str, username: str):
    logger.info("Starting Across Protocol Bot with README format")
    logger.info(f"Processing query: {user_query}")
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    embeddings_path = os.path.join('knowledge_base', 'embeddings', 'merged_knowledge_base_embeddings.json')
    logger.info(f"Loading embeddings from: {embeddings_path}")

    try:
        embeddings_list = load_embeddings(embeddings_path)
        logger.info("Successfully loaded embeddings.")
    except Exception as e:
        logger.error(f"Failed to load embeddings: {str(e)}")
        return "# Error\n\nFailed to retrieve embeddings from file and MongoDB."

    try:
        query_embedding = generate_embedding_for_query(client, user_query)
        most_similar_docs = find_most_similar_documents(query_embedding, embeddings_list, user_query, top_n=3)
        logger.info(f"Found {len(most_similar_docs)} most similar documents.")

        context = generate_context_from_documents(most_similar_docs)
        logger.info(f"Generated context with {len(context)} characters.")

        references = extract_references(context)
        logger.info(f"Extracted {len(references)} unique references.")

        # Use README-specific template
        messages = format_query_for_readme(context, user_query)

        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=1000,  # Increased for README format
            temperature=0.15,
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Format the response with references if they're not already included
        final_response = format_response_with_references(response_text, references)
        
        log_query_and_response(user_query, final_response, username)
        
        return final_response

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "# Error\n\nSorry, there was an error generating the response."


def generate_response_with_context(user_query: str, username: str):
    logger.info("Starting Across Protocol Bot")
    logger.info(f"Processing query: {user_query}")
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    embeddings_path = os.path.join('knowledge_base', 'embeddings', 'merged_knowledge_base_embeddings.json')
    logger.info(f"Loading embeddings from: {embeddings_path}")

    try:
        embeddings_list = load_embeddings(embeddings_path)
        logger.info("Successfully loaded embeddings.")
    except Exception as e:
        logger.error(f"Failed to load embeddings: {str(e)}")
        return "Failed to retrieve embeddings from file and MongoDB."


    query_embedding = generate_embedding_for_query(client, user_query)

    most_similar_docs = find_most_similar_documents(query_embedding, embeddings_list, user_query, top_n=3)
    logger.info(f"Found {len(most_similar_docs)} most similar documents.")

    context = generate_context_from_documents(most_similar_docs)
    logger.info(f"Generated context with {len(context)} characters.")

    messages = generate_prompt_template(context, user_query)

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=800,
            temperature=0.15,
        )
        response_text = response.choices[0].message.content.strip()
        log_query_and_response(user_query, response_text, username)
        return response_text

    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "Sorry, there was an error generating the response."

