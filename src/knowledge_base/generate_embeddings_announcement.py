import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import logging
from pymongo import MongoClient

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB Setup
client_mongo = MongoClient(os.getenv('MONGO_URI'))
db = client_mongo.get_database('knowledge_base')
collection = db.get_collection('announcements')
embedded_collection = db.get_collection('announcement_embedded')

# Function to load announcements from MongoDB
def load_announcements():
    """Load announcements from MongoDB collection."""
    announcements = list(collection.find({}))
    logger.info(f"Loaded {len(announcements)} announcements from MongoDB.")
    return announcements

# Function to generate embedding
def generate_embedding(content):
    """Generate embedding using OpenAI API."""
    try:
        response = client.embeddings.create(
            input=content,
            model='text-embedding-ada-002'
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {str(e)}")
        return None

# Function to format content for embedding
def extract_content_for_embedding(content):
    """Format content for embedding generation."""
    if isinstance(content, str):
        return content[:30000]  # Limit to 30,000 characters

    parts = []
    if isinstance(content, dict):
        if 'title' in content:
            parts.append(f"Title: {content['title']}")
        if 'headers' in content:
            for header in content['headers']:
                parts.append(f"Section: {header}")
        if 'paragraphs' in content:
            for para in content['paragraphs']:
                parts.append(para)
        if 'lists' in content:
            for list_item in content['lists']:
                parts.append(list_item)

    combined_content = " ".join(parts)
    return combined_content[:30000]  # Limit to 30,000 characters

# Function to generate embeddings for all announcements
def generate_embeddings_for_announcements(announcements):
    """Generate embeddings for all announcements."""
    embeddings_list = []

    for announcement in announcements:
        try:
            content = announcement.get('content', "")
            formatted_content = extract_content_for_embedding(content)

            if formatted_content.strip():
                embedding = generate_embedding(formatted_content)
                if embedding:
                    embeddings_list.append({
                        'url': announcement.get('url'),
                        'embedding': embedding,
                        'content': formatted_content
                    })
                    logger.info(f"Generated embedding for: {announcement.get('url')}")
                else:
                    logger.warning(f"Skipping {announcement.get('url')} - failed to generate embedding.")
            else:
                logger.warning(f"Skipping {announcement.get('url')} - no relevant content.")
        except Exception as e:
            logger.error(f"Error processing announcement {announcement.get('url')}: {str(e)}")

    logger.info(f"Generated embeddings for {len(embeddings_list)} announcements.")
    return embeddings_list

# Function to append to or create simple JSON file
def save_simple_json(announcements, output_file):
    """Save simple announcements JSON (append to file if exists)."""
    for announcement in announcements:
        if '_id' in announcement:
            announcement['_id'] = str(announcement['_id'])  # Convert ObjectId to string

    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
            announcements = existing_data + announcements
        except Exception as e:
            logger.error(f"Error reading existing file {output_file}: {str(e)}")

    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(announcements, file, ensure_ascii=False, indent=4)
        logger.info(f"Simple announcements saved to {output_file}.")
    except Exception as e:
        logger.error(f"Error saving simple JSON: {str(e)}")

# Function to append to or create embeddings JSON file
def save_embeddings_json(embeddings_list, output_file):
    """Save embeddings JSON (append to file if exists)."""
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
            embeddings_list = existing_data + embeddings_list
        except Exception as e:
            logger.error(f"Error reading existing file {output_file}: {str(e)}")

    try:
        with open(output_file, 'w', encoding='utf-8') as file:
            json.dump(embeddings_list, file, ensure_ascii=False, indent=4)
        logger.info(f"Embeddings saved to {output_file}.")
    except Exception as e:
        logger.error(f"Error saving embeddings JSON: {str(e)}")

# Function to save embeddings to MongoDB
def save_embeddings_to_mongodb(embeddings_list):
    """Save embeddings to MongoDB collection."""
    try:
        embedded_collection.insert_many(embeddings_list)
        logger.info(f"Embeddings successfully saved to MongoDB collection: {embedded_collection.name}.")
    except Exception as e:
        logger.error(f"Error saving embeddings to MongoDB: {str(e)}")

# Function to generate embeddings for announcements and save them
def generate_embeddings_announcement(data):
    """Generate embeddings for announcements and save them."""
    # Define the path to the announcements folder inside knowledge_base
    announcements_folder = os.path.join('knowledge_base', 'announcements')

    # Ensure the announcements folder exists
    if not os.path.exists(announcements_folder):
        os.makedirs(announcements_folder)

    # Generate embeddings
    embeddings = generate_embeddings_for_announcements(data)

    # Define file paths
    simple_json_path = os.path.join(announcements_folder, 'simple_announcements.json')
    embeddings_json_path = os.path.join(announcements_folder, 'embeddings_announcements.json')

    # Save simple announcements JSON locally
    save_simple_json(data, simple_json_path)

    # Save embeddings JSON locally
    save_embeddings_json(embeddings, embeddings_json_path)

    # Save embeddings to MongoDB
    save_embeddings_to_mongodb(embeddings)

    logger.info(f"All files saved successfully in {announcements_folder}.")

# Main function
if __name__ == "__main__":
    announcements = load_announcements()

    # Generate embeddings and save them
    generate_embeddings_announcement(announcements)

    logger.info("Embedding generation process completed.")
