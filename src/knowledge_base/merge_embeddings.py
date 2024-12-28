import os
import json
import shutil
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
temp_file_path = merged_file_path + ".tmp"

# Write to temporary file
try:
    with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
        json.dump(merged_data, temp_file, indent=4, ensure_ascii=False)
    logger.info(f"Temporary file '{temp_file_path}' created successfully.")
    
    # Atomically replace the target file with the temporary file
    shutil.move(temp_file_path, merged_file_path)
    logger.info(f"Temporary file '{temp_file_path}' renamed to '{merged_file_path}'.")
except Exception as e:
    logger.error(f"Failed to write or rename file: {e}")
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
        logger.info(f"Cleaned up temporary file '{temp_file_path}'.")

# Update MongoDB
collection.delete_many({})

try:
    if merged_data:
        collection.insert_many(merged_data)
        logger.info("Merged data has been successfully uploaded to MongoDB.")
    else:
        logger.warning("No data to upload to MongoDB.")
except Exception as e:
    logger.error(f"Error uploading data to MongoDB: {e}")
