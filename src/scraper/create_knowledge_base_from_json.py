import json
from loguru import logger
from bs4 import BeautifulSoup

def load_knowledge_base(file_path):
    """Load the knowledge base from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_important_info(html_content):
    """Extract key information from HTML content."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    info = {
        "title": soup.title.string if soup.title else "No title",
        "headers": [header.get_text() for header in soup.find_all(['h1', 'h2', 'h3'])],
        "paragraphs": [para.get_text() for para in soup.find_all('p')],
        "lists": [ul.get_text(separator='\n').strip() for ul in soup.find_all('ul')],
        "tables": [],
        "code_blocks": [],
        "summaries": []
    }
    
    for table in soup.find_all('table'):
        table_data = []
        for row in table.find_all('tr'):
            row_data = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
            table_data.append(row_data)
        info["tables"].append(table_data)

    for code in soup.find_all('code', id=True):  
        info["code_blocks"].append({
            "id": code['id'],
            "code": code.get_text().strip()
        })
    
    for summary in soup.find_all('summary'):
        info["summaries"].append(summary.get_text().strip())
    
    return info

def process_knowledge_base(knowledge_base):
    """Process the knowledge base sequentially."""
    processed_data = {}
    for url, html_content in knowledge_base.items():
        processed_data[url] = extract_important_info(html_content)
    return processed_data

def save_processed_data(processed_data, output_file):
    """Save the processed data to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)

def process_and_save_knowledge_base(input_file, output_file):
    """Load, process, and save the knowledge base for a specific version."""
    knowledge_base = load_knowledge_base(input_file)
    processed_data = process_knowledge_base(knowledge_base)
    save_processed_data(processed_data, output_file)

knowledge_bases = [
    {"input_file": "scraper/v3/scraped_data_v3.json", "output_file": "knowledge_base/embeddings/v3/knowledge_base_v3.json"},
    {"input_file": "scraper/v2/scraped_data_v2.json", "output_file": "knowledge_base/embeddings/v2/knowledge_base_v2.json"},
    {"input_file": "scraper/user_docs/scraped_data_user_docs.json", "output_file": "knowledge_base/embeddings/user_docs/knowledge_base_user_docs.json"}
]

for kb in knowledge_bases:
    logger.info(f"Processing {kb['input_file']}...")
    process_and_save_knowledge_base(kb['input_file'], kb['output_file'])

logger.info("All knowledge bases processed successfully!")
