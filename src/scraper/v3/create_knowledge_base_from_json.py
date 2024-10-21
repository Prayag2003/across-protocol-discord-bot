import json
from bs4 import BeautifulSoup

def load_knowledge_base(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_important_info(html_content):
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
    
    # Extract summary elements
    for summary in soup.find_all('summary'):
        info["summaries"].append(summary.get_text().strip())
    
    return info

def process_knowledge_base(knowledge_base):
    processed_data = {}
    for url, html_content in knowledge_base.items():
        processed_data[url] = extract_important_info(html_content)
    return processed_data

def save_processed_data(processed_data, output_file):
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    knowledge_base = load_knowledge_base("scraper/v3/scraped_data_v3.json")
    processed_data = process_knowledge_base(knowledge_base)
    save_processed_data(processed_data, "knowledge_base/embeddings/v3/knowledge_base_v3.json")