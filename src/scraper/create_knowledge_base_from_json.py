import json
from loguru import logger
from bs4 import BeautifulSoup

def load_knowledge_base(file_path):
    """Load the knowledge base from a JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_important_info(html_content, redundant_data):
    """Extract key information from HTML content and remove redundant data."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Split redundant_data into a list of items to remove
    redundant_data_list = [line.strip() for line in redundant_data.split('\n') if line.strip()]
    
    info = {
        "title": soup.title.string if soup.title else "No title",
        "headers": [header.get_text() for header in soup.find_all(['h1', 'h2', 'h3'])],
        "paragraphs": [para.get_text() for para in soup.find_all('p')],
        "lists": [ul.get_text(separator='\n').strip() for ul in soup.find_all('ul')],
        "tables": [],
        "code_blocks": [],
    }
    
    # Remove redundant data from headers and paragraphs
    info["headers"] = [header for header in info["headers"] if not any(redundant in header for redundant in redundant_data_list)]
    info["paragraphs"] = [para for para in info["paragraphs"] if not any(redundant in para for redundant in redundant_data_list)]
    info["lists"] = [ul for ul in info["lists"] if not any(redundant in ul for redundant in redundant_data_list)]

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

    return info

def process_knowledge_base(knowledge_base, redundant_data):
    """Process the knowledge base sequentially."""
    processed_data = {}
    for url, html_content in knowledge_base.items():
        processed_data[url] = extract_important_info(html_content, redundant_data)
    return processed_data

def save_processed_data(processed_data, output_file):
    """Save the processed data to a JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(processed_data, f, ensure_ascii=False, indent=4)

def process_and_save_knowledge_base(input_file, output_file, redundant_data):
    """Load, process, and save the knowledge base for a specific version."""
    knowledge_base = load_knowledge_base(input_file)
    processed_data = process_knowledge_base(knowledge_base, redundant_data)
    save_processed_data(processed_data, output_file)

# Define the redundant data to be removed
redundant_data = """👋
Introduction
Getting Started
What is Across?
Technical FAQ
Migration Guides
Migration from V2 to V3
Migration to CCTP
Migration Guide for Relayers
Migration Guide for API Users
🔗
Use Cases
Instant Bridging in your Application
Bridge Integration Guide
Multi Chain Bridge UI Guide
Single Chain Bridge UI Guide
Embedded Cross-chain Actions
Cross-chain Actions Integration Guide
Using the Generic Multicaller Handler Contract
Using a Custom Handler Contract
Cross-chain Actions UI Guide
Settle Cross-chain Intents
🧠
Concepts
What are Cross-chain Intents?
Intents Architecture in Across
Intent Lifecycle in Across
Canonical Asset Maximalism
🛠️
Reference
API Reference
SDK Reference
Contracts
Arbitrum (Chain ID: 42161)
Base (Chain ID: 8453)
Blast (Chain ID: 81457)
Ethereum Mainnet (Chain ID: 1)
Linea (Chain ID: 59144)
Lisk (Chain ID: 1135)
Mode (Chain ID: 34443)
Optimism (Chain ID: 10)
Polygon (Chain ID: 137)
Redstone (Chain ID: 690)
Scroll (Chain ID: 534352)
World Chain (Chain ID: 480)
zkSync (Chain ID: 324)
Zora (Chain ID: 7777777)
Sepolia Testnet
Selected Contract Functions
Supported Chains
Fees in the System
Actors in the System
Security Model and Verification
Disputing Root Bundles
Validating Root Bundles
Tracking Events
🔁
Relayers
Running a Relayer
Relayer Exclusivity
📚
Resources
Release Notes
Developer Support
Bug Bounty
Audits
New Chain Requests"""

knowledge_bases = [
    {"input_file": "scraper/v3/scraped_data_v3.json", "output_file": "knowledge_base/embeddings/v3/knowledge_base_v3.json"},
    {"input_file": "scraper/v2/scraped_data_v2.json", "output_file": "knowledge_base/embeddings/v2/knowledge_base_v2.json"},
    {"input_file": "scraper/user_docs/scraped_data_user_docs.json", "output_file": "knowledge_base/embeddings/user_docs/knowledge_base_user_docs.json"}
]

for kb in knowledge_bases:
    logger.info(f"Processing {kb['input_file']}...")
    process_and_save_knowledge_base(kb['input_file'], kb['output_file'], redundant_data)

logger.info("All knowledge bases processed successfully!")
