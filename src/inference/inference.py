import os
import json
import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

def load_embeddings(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def detect_query_type(query):
    """
    Detect if the query is code-related or explanation-related
    """
    code_indicators = [
        'code', 'function', 'implement', 'write', 'program',
        'syntax', 'debug', 'error', 'example', 'script'
    ]
    
    query_lower = query.lower()
    return any(indicator in query_lower for indicator in code_indicators)

def get_coding_template():
    """
    Return a template focused on code generation
    """
    return """You are an expert developer focusing on the Across protocol implementation.
    Please provide practical, production-ready code solutions with:
    - Clear documentation and comments
    - Error handling and edge cases
    - Best practices and optimizations
    - Example usage where appropriate
    
    Focus on writing clean, maintainable code that follows industry standards."""

def get_explanation_template():
    """
    Return a template focused on explanations
    """
    return """You are a knowledgeable assistant specializing in the Across protocol and its related technologies.
    Please provide clear, informative responses that:
    - Break down complex concepts into understandable parts
    - Use analogies and examples where helpful
    - Focus on practical understanding
    - Address the core of the user's question
    
    Aim to educate and clarify rather than just provide information."""

def get_prompt_template(context, query):
    """
    Generate a context-aware prompt template based on query type
    """
    is_code_query = detect_query_type(query)
    
    system_message = get_coding_template() if is_code_query else get_explanation_template()
    
    user_message = f"""Context:
    {context}

    User Query:
    {query}
    
    {'Please provide a code solution with explanations.' if is_code_query else 'Please explain this clearly and comprehensively.'}"""
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

def generate_response_with_context(context, query):
    messages = get_prompt_template(context, query)
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=600,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating response: {str(e)}")
        return "Sorry, there was an error generating the response."

def generate_embedding_for_query(query):
    response = client.embeddings.create(
        input=query,
        model='text-embedding-ada-002'
    )
    return response.data[0].embedding

def compute_similarity(query_embedding, embeddings_list):
    similarities = []

    for entry in embeddings_list:
        for url, embedding in entry.items():
            embedding_array = np.array(embedding)
            query_embedding_array = np.array(query_embedding)

            similarity = cosine_similarity([query_embedding_array], [embedding_array])[0][0]
            similarities.append((url, similarity))

    return similarities

def find_most_similar_documents(query_embedding, embeddings_list, top_n=3):
    similarities = compute_similarity(query_embedding, embeddings_list)
    sorted_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
    print("sorted_similarities:", sorted_similarities[:top_n])
    return sorted_similarities[:top_n]


if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    embeddings_path = os.path.join('..', 'scraper', 'knowledge_base', 'knowledge_base_embeddings.json')
    embeddings_list = load_embeddings(embeddings_path)

    user_query = "What is internal structure of across in detail?"

    query_embedding = generate_embedding_for_query(user_query)
    most_similar_docs = find_most_similar_documents(query_embedding, embeddings_list, top_n=3)

    context = "\n\n".join([f"URL: {url}\n" for url, _ in most_similar_docs])

    response = generate_response_with_context(context, user_query)
    print(f"Response:\n{response}")