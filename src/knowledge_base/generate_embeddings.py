import os
import json
from openai import OpenAI   
from dotenv import load_dotenv
load_dotenv()

def load_knowledge_base(file_path):
    """Load and validate knowledge base content"""
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def extract_content_for_embedding(content):
    """Extract and format content for embedding generation"""
    parts = []
    
    if content.get('title'):
        parts.extend([content['title']] * 3)
    
    if content.get('headers'):
        parts.extend([f"Section: {header}" for header in content['headers']] * 2)
    
    if content.get('paragraphs'):
        parts.extend(content['paragraphs'])
    
    if content.get('lists'):
        formatted_lists = []
        for list_item in content['lists']:
            items = [item.strip() for item in list_item.split('\n') if item.strip()]
            formatted_lists.extend(items)
        parts.extend(formatted_lists)
    
    combined_content = " ".join(parts)
    
    max_chars = 6000  
    if len(combined_content) > max_chars:
        combined_content = combined_content[:max_chars]
    
    return combined_content

def create_embeddings_for_kb(knowledge_base):
    """Generate embeddings with improved content processing"""
    embeddings_list = []

    for url, content in knowledge_base.items():  
        try:
            if content:  
                paragraphs = content.get('paragraphs', [])
                
                formatted_content = ' '.join(paragraphs)
                
                if formatted_content.strip():  
                    embedding = generate_embedding(formatted_content)
                    embeddings_list.append({
                        'url': url,
                        'embedding': embedding,
                    })
                    print(f"Generated embedding for: {url}")
                else:
                    print(f"Skipping {url} - no content to embed")
            else:
                print(f"Skipping {url} - content is missing")
        except Exception as e:
            print(f"Error processing {url}: {str(e)}")
    
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
    print(f"Embeddings saved to {output_file}")

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
        print(f"Loaded knowledge base from {knowledge_base_path} with {len(knowledge_base)} entries")

        embeddings_list = create_embeddings_for_kb(knowledge_base)
        print(f"Generated {len(embeddings_list)} embeddings for {knowledge_base_path}")

        save_embeddings(embeddings_list, embeddings_output_path)

    print("Embedding generation process completed for all knowledge bases.")