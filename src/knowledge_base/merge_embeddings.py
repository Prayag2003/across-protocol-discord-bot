import os
import json

file_paths = [
    'knowledge_base/embeddings/v3/knowledge_base_v3_embeddings.json',
    'knowledge_base/embeddings/v2/knowledge_base_v2_embeddings.json',
    'knowledge_base/embeddings/user_docs/knowledge_base_user_docs_embeddings.json',
]

merged_data = []

for file_path in file_paths:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file) 
            
            if isinstance(data, list):
                merged_data.extend(data)  
            else:
                merged_data.append(data)  

with open('knowledge_base/embeddings/merged_knowledge_base_embeddings.json', 'w', encoding='utf-8') as merged_file:
    json.dump(merged_data, merged_file, indent=4, ensure_ascii=False)

print("Data from all files has been merged successfully into 'merged_knowledge_base_embeddings.json'")
