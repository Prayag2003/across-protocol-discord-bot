import re
from typing import Optional, Tuple, List, Dict

def get_language_from_codeblock(text: str) -> str:
    match = re.match(r"```(\w+)", text)
    if match:
        language = match.group(1).lower()
        # Normalize common aliases
        if language in ["sh", "bash"]:
            return "shell"
        return language
    return "txt"

def     get_file_extension(language: str) -> str:
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
        "html": "html",
        "css": "css",
        "java": "java",
        "cpp": "cpp",
    }
    return extensions.get(language.lower(), "txt")

def chunk_message(response: str) -> List[str]:
    """
    Split a long message into chunks by paragraphs to fit Discord's character limit.
    """
    return chunk_message_by_paragraphs(response)

def chunk_message_by_paragraphs(message: str, max_chunk_size: int = 1980) -> List[str]:
    """
    Split a message into smaller chunks by paragraphs while respecting the max_chunk_size.
    """
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

def extract_code_blocks(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Extract code blocks from the given text and return the remaining text and code blocks.
    """
    code_blocks = []
    cleaned_text = ""
    pattern = r"```(\w+)?\n(.*?)```"

    last_end = 0
    for match in re.finditer(pattern, text, re.DOTALL):
        # Add text before the code block to cleaned_text
        cleaned_text += text[last_end:match.start()]
        language = match.group(1) or "txt"
        code = match.group(2).strip()
        if code:  # Only include non-empty code blocks
            code_blocks.append({"code": code, "language": language})
        last_end = match.end()

    # Append the remaining text after the last code block
    cleaned_text += text[last_end:]
    return cleaned_text.strip(), code_blocks
