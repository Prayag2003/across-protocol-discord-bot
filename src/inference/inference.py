import re
import os
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

def get_latest_fine_tuned_model() -> str:
    try:
        with open("latest_model.txt", "r") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            if lines:
                return lines[-1]  # The last model ID
    except FileNotFoundError:
        logger.warning("No fine-tuned model found. Using default model.")
    except Exception as e:
        logger.error(f"Error reading fine-tuned model file: {e}")    
    return "gpt-4o-2024-08-06"

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

def generate_context_from_documents(similar_docs, max_length=2000):
    """Generate optimized context from similar documents including embedding content"""
    logger.info("Generating context from similar documents...")
    context_parts = []
    current_length = 0
    
    for url, similarity, content in similar_docs:
        if current_length >= max_length:
            break
            
        formatted_content = (
            f"**Source**: [{url}]({url})  \n"
            f"**Similarity**: {similarity:.2f}  \n"
            f"**Content**: {content}\n"
        )
        context_parts.append(formatted_content)
        current_length += len(formatted_content)
    
    return "\n\n".join(context_parts)

_openai_client = None

def get_openai_client():
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        logger.info("Initialized OpenAI client")
    return _openai_client

def generate_response_with_context(user_query: str, username: str):
    logger.info(f"Processing query: {user_query}")
    client = get_openai_client()

    model_name = get_latest_fine_tuned_model()
    logger.info(f"Using model: {model_name}")

    embeddings_path = os.path.join('knowledge_base', 'embeddings', 'merged_knowledge_base_embeddings.json')

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

    # First API Call: Generate the main response based on query and context
    messages = generate_prompt_template(context, user_query)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            max_tokens=1000,
            temperature=0.15,
        )

        # The main response generated from the first API call
        response_text = response.choices[0].message.content.strip()
        logger.info(f"Generated response of: {len(response_text)} chars")

        # Second API Call: Extract topics and tags
        analysis_prompt = f"""
        Analyze this query and:
        1. Extract the main topic(s) being discussed.
        2. Provide 1-3 relevant tags that emerge naturally from the content.
        Return as JSON with these keys: topics, tags
        Query: {user_query}
        """

        try:
            analysis_response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": analysis_prompt}],
                max_tokens=100,
                temperature=0.15,
            )

            raw_analysis_response = analysis_response.choices[0].message.content.strip()
            logger.info(f"Raw analysis response: {raw_analysis_response}")

            # Remove 'json' prefix and backticks
            cleaned_response = re.sub(r'^(?:json\s*)?```(?:json\s*)?|```$', '', raw_analysis_response)
            cleaned_response = cleaned_response.strip()

            if not cleaned_response:
                logger.error("Received empty response for topics and tags analysis")
                return "Sorry, there was an error processing the analysis."

            try:
                analysis_json = json.loads(cleaned_response)
                topics = analysis_json.get('topics', [])
                tags = analysis_json.get('tags', [])

                log_query_and_response(user_query, response_text, username, topics, tags)
                return response_text

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}. Cleaned response: {cleaned_response}")
                return response_text  # Return main response even if analysis fails

        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return "Sorry, there was an error generating the response."
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "Sorry, there was an error generating the response."


# def generate_response_with_context(user_query: str, username: str):

#     logger.info(f"Processing query: {user_query}")
#     client = get_openai_client()

#     model_name = get_latest_fine_tuned_model()
#     logger.info(f"Using model: {model_name}")

#     embeddings_path = os.path.join('knowledge_base', 'embeddings', 'merged_knowledge_base_embeddings.json')

#     try:
#         embeddings_list = load_embeddings(embeddings_path)
#         logger.info("Successfully loaded embeddings.")
#     except Exception as e:
#         logger.error(f"Failed to load embeddings: {str(e)}")
#         return "Failed to retrieve embeddings from file and MongoDB."

#     query_embedding = generate_embedding_for_query(client, user_query)
#     most_similar_docs = find_most_similar_documents(query_embedding, embeddings_list, user_query, top_n=3)
#     logger.info(f"Found {len(most_similar_docs)} most similar documents.")

#     context = generate_context_from_documents(most_similar_docs)
#     logger.info(f"Generated context with {len(context)} characters.")

#     messages = generate_prompt_template(context, user_query)

#     try:
#         response = client.chat.completions.create(
#             model=model_name,
#             messages=messages,
#             max_tokens=1000,
#             temperature=0.15,
#         )

#         response_text = response.choices[0].message.content.strip()
#         logger.info(f"Generated response.")
#         log_query_and_response(user_query, response_text, username)
#         return response_text

#     except Exception as e:
#         logger.error(f"Error generating response: {str(e)}")
#         return "Sorry, there was an error generating the response."