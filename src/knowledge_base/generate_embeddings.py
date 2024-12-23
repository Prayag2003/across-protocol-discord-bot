import os
import json
from openai import OpenAI   
from loguru import logger
from dotenv import load_dotenv
from loguru import logger
load_dotenv()

def load_knowledge_base(file_path):
    """Load and validate knowledge base content"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def extract_content_for_embedding(content):
    """Extract and format content for embedding generation with descriptive labels."""
    parts = []
    used_titles = set()

    # Check if all fields are empty
    if not any(content.values()):
        logger.info("No relevant content fields found.")
        return ""

    # Add the title once with a label
    if content.get('title') and content['title'] not in used_titles:
        parts.append(f"Title: {content['title']}")
        used_titles.add(content['title'])
    
    # Add headers with labels, no repetition
    if content.get('headers'):
        for header in content['headers']:
            parts.append(f"Section: {header}")
            parts.append('---')
    
    # Add paragraphs directly
    if content.get('paragraphs'):
        for para in content['paragraphs']:
            parts.append(para)
        parts.append('---')
    
    # Add code blocks
    if content.get('code_blocks'):
        for block in content['code_blocks']:
            parts.append(f"Code Block ID: {block['id']}")
            parts.append(block['code'])
        parts.append('---')

    # Process tables to ensure items are strings
    if content.get('tables'):
        for table in content['tables']:
            parts.append("Table:")
            for row in table:
                parts.append(f"Field: {row[0]}")
                parts.append(f"Description: {row[1]}")
        parts.append('---')

    # Process lists to ensure items are strings
    if content.get('lists'):
        formatted_lists = []
        for list_item in content['lists']:
            if isinstance(list_item, str):
                items = [item.strip() for item in list_item.split('\n') if item.strip()]
                formatted_lists.extend(items)
            elif isinstance(list_item, list):  # Handle nested lists
                formatted_lists.extend([str(sub_item) for sub_item in list_item if isinstance(sub_item, str)])
        parts.extend(formatted_lists)
        parts.append('---')    

    # Join all parts into a single content string
    combined_content = " ".join(parts)
    
    # Limit to a max of 30,000 characters if necessary
    max_chars = 30000
    if len(combined_content) > max_chars:
        combined_content = combined_content[:max_chars]

    logger.info(combined_content)
    return combined_content


# def extract_content_for_embedding(content):
#     """Extract and format content for embedding generation with descriptive labels."""
#     parts = []
    
#     # Add the title once with a label
#     if content.get('title'):
#         parts.append(f"Title: {content['title']}")
    
#     # Add headers with labels, no repetition
#     if content.get('headers'):
#         parts.extend([f"Section: {header}" for header in content['headers'] if isinstance(header, str)])
    
#     # Add paragraphs directly
#     if content.get('paragraphs'):
#         parts.extend([para for para in content['paragraphs'] if isinstance(para, str)])
    
#     # Add code blocks
#     if content.get('code_blocks'):
#         parts.extend([code for code in content['code_blocks'] if isinstance(code, dict)])

#     # Process lists to ensure items are strings
#     if content.get('lists'):
#         formatted_lists = []
#         for list_item in content['lists']:
#             if isinstance(list_item, str):
#                 items = [item.strip() for item in list_item.split('\n') if item.strip()]
#                 formatted_lists.extend(items)
#             elif isinstance(list_item, list):  # Handle nested lists
#                 formatted_lists.extend([str(sub_item) for sub_item in list_item if isinstance(sub_item, str)])
#         parts.extend(formatted_lists)

#     # Process tables to ensure items are strings
#     if content.get('tables'):
#         for table in content['tables']:
#             if isinstance(table, list):
#                 parts.extend([str(cell) for row in table for cell in row if isinstance(cell, str)])
#             elif isinstance(table, str):
#                 parts.append(table)

#     # Join all parts into a single content string
#     combined_content = " ".join(parts)
    
#     # Limit to a max of 30,000 characters if necessary
#     max_chars = 30000
#     if len(combined_content) > max_chars:
#         combined_content = combined_content[:max_chars]
    
#     return combined_content

def create_embeddings_for_kb(knowledge_base):
    """Generate embeddings with improved content processing"""
    embeddings_list = []

    for url, content in knowledge_base.items():  
        try:
            if content:  
                formatted_content = extract_content_for_embedding(content)
                
                if formatted_content.strip():  
                    embedding = generate_embedding(formatted_content)
                    embeddings_list.append({
                        'url': url,
                        'embedding': embedding,
                        'content': formatted_content 
                    })
                    logger.info(f"Generated embedding for: {url}")
                else:
                    logger.warning(f"Skipping {url} - no content to embed")

            else:
                logger.warning(f"Skipping {url} - content is missing")

        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
    
    return embeddings_list

def generate_embedding(content):
    try:
        response = client.embeddings.create(
            input=content,
            model='text-embedding-ada-002'
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Error generating embedding: {str(e)}")

def save_embeddings(embeddings_list, output_file):
    """Save embeddings with proper formatting"""
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(embeddings_list, file, ensure_ascii=False, indent=4)
    logger.info(f"Embeddings saved to {output_file}")

if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    
    knowledge_base_paths = [
        {
            "input": os.path.join('knowledge_base', 'embeddings', 'v2', 'knowledge_base_v2.json'),
            "output": os.path.join('knowledge_base', 'embeddings', 'v2', 'knowledge_base_v2_embeddings.json')
        },
        {
            "input": os.path.join('knowledge_base', 'embeddings', 'v3', 'knowledge_base_v3.json'),
            "output": os.path.join('knowledge_base', 'embeddings', 'v3', 'knowledge_base_v3_embeddings.json')
        },
        {
            "input": os.path.join('knowledge_base', 'embeddings', 'user_docs', 'knowledge_base_user_docs.json'),
            "output": os.path.join('knowledge_base', 'embeddings', 'user_docs', 'knowledge_base_user_docs_embeddings.json')
        }
    ]
    
    for kb_paths in knowledge_base_paths:
        knowledge_base_path = kb_paths["input"]
        embeddings_output_path = kb_paths["output"]

        knowledge_base = load_knowledge_base(knowledge_base_path)
        logger.info(f"Loaded knowledge base from {knowledge_base_path} with {len(knowledge_base)} entries")

        embeddings_list = create_embeddings_for_kb(knowledge_base)
        logger.info(f"Generated {len(embeddings_list)} embeddings for {knowledge_base_path}")

        save_embeddings(embeddings_list, embeddings_output_path)

    logger.info("Embedding generation process completed for all knowledge bases.")
