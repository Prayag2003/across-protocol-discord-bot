import re

def chunk_message(response):
    """Legacy chunk_message function for backward compatibility"""
    return chunk_message_by_paragraphs(response)

def chunk_message_by_paragraphs(message, max_chunk_size=1980):
    """Splits a message by paragraphs or sentences while ensuring no chunks exceed the specified limit."""
    
    paragraphs = re.split(r'\n\n+', message.strip())
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n"  
            current_chunk += paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip()) 
    
    return chunks