import re
from typing import Optional, Tuple, Dict

def get_language_from_codeblock(text: str) -> str:
    match = re.match(r"```(\w+)", text)
    return match.group(1) if match else "txt"

def get_file_extension(language: str) -> str:
    extensions = {
        "javascript": "js",
        "typescript": "ts",
        "python": "py",
        "go": "go",
        "rust": "rs",
        "solidity": "sol",
        "sql": "sql",
        "xml": "xml",
        "yaml": "yaml",
        "json": "json",
        "markdown": "md",
        "shell": "sh",
        "bash": "sh",
    }
    return extensions.get(language.lower(), "txt")
def chunk_message(response):
    return chunk_message_by_paragraphs(response)

def chunk_message_by_paragraphs(message, max_chunk_size=1980):
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

def extract_code_blocks(text: str) -> Tuple[str, list]:
    code_blocks = []
    cleaned_text = ""
    pattern = r"```(\w+)?\n(.*?)```"
    
    last_end = 0
    for match in re.finditer(pattern, text, re.DOTALL):
        cleaned_text += text[last_end:match.start()]
        language = match.group(1) or "txt"
        code_blocks.append({"code": match.group(2).strip(), "language": language})
        last_end = match.end()
    
    cleaned_text += text[last_end:]
    return cleaned_text.strip(), code_blocks