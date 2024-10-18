import os
import json
from openai import OpenAI   
from dotenv import load_dotenv
load_dotenv()

def load_knowledge_base(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def create_embeddings_for_kb(knowledge_base):
    embeddings_list = [] 
    
    for entry in knowledge_base:
        print(f"Entry: {entry}")
        if isinstance(entry, dict):  
            for url, content in entry.items():
                embedding = generate_embedding(content)
                embeddings_list.append({url: embedding}) 
        elif isinstance(entry, str):
            embedding = generate_embedding(entry)
            embeddings_list.append({entry[:200]: embedding})  
        else:
            print(f"Unexpected entry type: {type(entry).__name__}")
        
    return embeddings_list

def generate_embedding(content):
    response = client.embeddings.create(
        input=content,
        model='text-embedding-ada-002'
    )
    return response.data[0].embedding

def save_embeddings(embeddings_list, output_file):
    with open(output_file, 'w', encoding='utf-8') as file:
        json.dump(embeddings_list, file, ensure_ascii=False, indent=4) 
    print(f"Embeddings saved to {output_file}")

if __name__ == "__main__":
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    knowledge_base_path = os.path.join('..', '..', 'scraper', 'knowledge_base', 'knowledge_base.json')
    embeddings_output_path = os.path.join('..', '..', 'scraper', 'knowledge_base', 'knowledge_base_embeddings.json')

    knowledge_base = load_knowledge_base(knowledge_base_path)  
    embeddings_list = create_embeddings_for_kb(knowledge_base)
    
    save_embeddings(embeddings_list, embeddings_output_path)
