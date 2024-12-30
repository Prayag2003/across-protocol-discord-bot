import os
from dotenv import load_dotenv
from datetime import datetime
from loguru import logger
from pymongo import MongoClient
load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DB_NAME")]
log_collection = db[os.getenv("LOGS_COLLECTION")]

def log_query_and_response(query, response, username, topics, tags):
    """Logs the query, response, and metadata to MongoDB."""
    timestamp = datetime.utcnow().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "username": username,
        "query": query,
        "response": response,
        "topics": topics,
        "tags": tags
    }
    
    try:
        log_collection.insert_one(log_entry)
        logger.info("Log successfully written to MongoDB.")
    except Exception as e:
        logger.error(f"Error writing log to MongoDB: {str(e)}")
