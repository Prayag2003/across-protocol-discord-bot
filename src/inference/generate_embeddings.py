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
            formatted_content = extract_content_for_embedding(content)
            if formatted_content.strip(): 
                embedding = generate_embedding(formatted_content)
                embeddings_list.append({
                    'url': url,
                    'embedding': embedding,
                    'content': {
                        'title': content.get('title', ''),
                        'headers': content.get('headers', []),
                        'paragraphs': content.get('paragraphs', []),
                        'lists': content.get('lists', [])
                    }
                })
                print(f"Generated embedding for: {url}")
            else:
                print(f"Skipping {url} - no content to embed")
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
    
    knowledge_base_path = os.path.join('..', 'knowledge_base', 'knowledge_base.json')
    embeddings_output_path = os.path.join('..', 'knowledge_base', 'knowledge_base_embeddings.json')

    knowledge_base = load_knowledge_base(knowledge_base_path)
    print(f"Loaded knowledge base with {len(knowledge_base)} entries")
    
    embeddings_list = create_embeddings_for_kb(knowledge_base)
    print(f"Generated {len(embeddings_list)} embeddings")
    
    save_embeddings(embeddings_list, embeddings_output_path)
    print("Process completed successfully!")