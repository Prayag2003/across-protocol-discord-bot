import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin, urlparse

def scrape_page(url):
    """Scrape a single page"""
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to retrieve {url}: {response.status_code}")
        return None

def extract_links(soup, base_url):
    """Extract links from the sidebar and correctly join relative links"""
    links = []
    for li in soup.select('.flex.flex-col a'):
        link = li.get('href')
        if link:
            print(link)
            full_link = urljoin(base_url, link) if not urlparse(link).netloc else link
            links.append(full_link)
    print(f"Found {len(links)} links for {base_url}")
    return links

def build_knowledge_base(BASE_URL: str, OUTPUT_FILE: str):
    """Build the knowledge base by scraping pages sequentially"""
    knowledge_base = {}
    main_page_html = scrape_page(BASE_URL)
    print("Base URL: ", BASE_URL)
    if main_page_html:
        knowledge_base[BASE_URL] = main_page_html 

        soup = BeautifulSoup(main_page_html, 'html.parser')
        links = extract_links(soup, BASE_URL)

        for link in links:
            page_html = scrape_page(link)
            if page_html:
                knowledge_base[link] = page_html  

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=4)
    
    print(f"Knowledge base saved to {OUTPUT_FILE}\n\n")

def run_scrapers_sequentially():
    """Run the scrapers sequentially"""
    scrapers = [
        {"BASE_URL": "https://docs.across.to/", "OUTPUT_FILE": "scraper/v3/scraped_data_v3.json"},
        {"BASE_URL": "https://docs.across.to/", "OUTPUT_FILE": "scraper/v2/scraped_data_v2.json"}, 
        {"BASE_URL": "https://docs.across.to/user-docs/", "OUTPUT_FILE": "scraper/user_docs/scraped_data_user_docs.json"} 
    ]
    
    for scraper in scrapers:
        build_knowledge_base(scraper["BASE_URL"], scraper["OUTPUT_FILE"])

run_scrapers_sequentially()
