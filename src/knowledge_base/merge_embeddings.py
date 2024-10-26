import os
import json
from dotenv import load_dotenv
from loguru import logger
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
collection = db[os.getenv("EMBEDDINGS_COLLECTION")]

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

merged_file_path = 'knowledge_base/embeddings/merged_knowledge_base_embeddings.json'
with open(merged_file_path, 'w', encoding='utf-8') as merged_file:
    json.dump(merged_data, merged_file, indent=4, ensure_ascii=False)

logger.info("Data from all files has been merged successfully into 'merged_knowledge_base_embeddings.json'")

# Remove existing documents in the MongoDB collection
collection.delete_many({})

# Upload merged data to MongoDB
try:
    if merged_data:
        collection.insert_many(merged_data)
        logger.info("Merged data has been successfully uploaded to MongoDB.")
    else:
        logger.warning("No data to upload to MongoDB.")
except Exception as e:
    logger.error(f"Error uploading data to MongoDB: {e}")
