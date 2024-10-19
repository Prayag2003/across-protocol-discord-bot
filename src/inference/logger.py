from loguru import logger
import json
import os

def format_response(response):
    formatted_response = response.replace("```", "\n```")  
    return formatted_response

def log_query_and_response(query, response):
    logger.info(f"Query: {query}")
    
    formatted_response = format_response(response)
    logger.info(f"Response:\n{formatted_response}")

    file_path = "query_response_log.json"
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, 'r', encoding='utf-8') as file:
            entries = json.load(file)
    else:
        entries = []

    entry = {
        "query": query,
        "response": formatted_response
    }
    entries.append(entry)

    with open(file_path, 'w', encoding='utf-8') as file:
        json.dump(entries, file, ensure_ascii=False, indent=4)
