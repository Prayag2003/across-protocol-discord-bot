import os
import json
import numpy as np
from openai import OpenAI
from loguru import logger
from dotenv import load_dotenv
load_dotenv()
from inference.logger import log_query_and_response
from sklearn.metrics.pairwise import cosine_similarity
from inference.template.prompt_template import generate_prompt_template

def load_embeddings(file_path):
    """Load embeddings with error handling"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        raise Exception(f"Error loading embeddings: {str(e)}")

def compute_similarity(query_embedding, embeddings_list, query):
    """Enhanced similarity computation"""
    similarities = []
    logger.info(f"Computing similarities for the query embedding...")
    query_terms = query.lower().split()

    for entry in embeddings_list:
        try:
            url = entry['url']
            embedding = entry['embedding']
            
            embedding_array = np.array(embedding)
            query_embedding_array = np.array(query_embedding)
            similarity = cosine_similarity([query_embedding_array], [embedding_array])[0][0]
            
            similarities.append((url, similarity, url))  
                
        except Exception as e:
            print(f"Error processing document {entry.get('url', 'unknown')}: {str(e)}")
            continue

    return similarities

def generate_context_from_documents(similar_docs, max_length=2000):
    """Generate optimized context from similar documents"""
    logger.info("Generating context from similar documents...")
    context_parts = []
    current_length = 0
    
    for url, similarity, _ in similar_docs:
        if current_length >= max_length:
            break
            
        formatted_content = f"Source ({similarity:.2f}): {url}"
        context_parts.append(formatted_content)
        current_length += len(formatted_content)
    
    return "\n\n".join(context_parts)

def find_most_similar_documents(query_embedding, embeddings_list, query, top_n=3):
    """Find most similar documents with improved filtering"""
    logger.info(f"Found top {top_n} similar documents...")
    similarities = compute_similarity(query_embedding, embeddings_list, query)
    
    filtered_similarities = [
        (url, sim, content) for url, sim, content in similarities 
        if sim > 0.3  
    ]
    
    sorted_similarities = sorted(filtered_similarities, key=lambda x: x[1], reverse=True)
    
    print("Similarity scores:")
    for url, sim, _ in sorted_similarities[:top_n]:
        print(f"{url}: {sim:.3f}")
    
    return sorted_similarities[:top_n]

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

def generate_response_with_context(user_query: str):
    logger.info("Starting Across Protocol Bot")
    print(f"Processing query: {user_query}")
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    embeddings_path = os.path.join('knowledge_base', 'embeddings', 'v3', 'knowledge_base_v3_embeddings.json')
    logger.info(f"Loading embeddings from: {embeddings_path}")

    try:
        embeddings_list = load_embeddings(embeddings_path)
        logger.info(f"Successfully loaded embeddings.")
    except Exception as e:
        logger.error(f"Failed to load embeddings: {str(e)}")
        exit(1)

    query_embedding = generate_embedding_for_query(client, user_query)

    most_similar_docs = find_most_similar_documents(query_embedding, embeddings_list, user_query, top_n=3)

    context = generate_context_from_documents(most_similar_docs)
    messages = generate_prompt_template(context, user_query)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=700,
            temperature=0.15,
        )
        response_text = response.choices[0].message.content.strip()
        log_query_and_response(user_query, response_text)
        return response_text

    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "Sorry, there was an error generating the response."