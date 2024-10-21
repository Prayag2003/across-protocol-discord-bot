import requests
from bs4 import BeautifulSoup
import json
import os

BASE_URL = "https://docs.across.to/"
OUTPUT_FILE = "scraper/v3/scraped_data_v3.json"

def scrape_page(url):
    response = requests.get(url)
    if response.status_code == 200:
        return response.text
    else:
        print(f"Failed to retrieve {url}: {response.status_code}")
        return None

def extract_links(soup):
    links = []
    for li in soup.select('.flex.flex-col a'):
        link = li.get('href')
        if link and link.startswith('/'):
            links.append(BASE_URL + link.lstrip('/'))  
    print(f"Found {len(links)} links")
    return links

def build_knowledge_base():
    knowledge_base = {}
    main_page_html = scrape_page(BASE_URL)
    
    if main_page_html:
        knowledge_base[BASE_URL] = main_page_html  

        soup = BeautifulSoup(main_page_html, 'html.parser')
        links = extract_links(soup)

        for link in links:
            page_html = scrape_page(link)
            if page_html:
                knowledge_base[link] = page_html  

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=4)
    
    print(f"Knowledge base saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    build_knowledge_base()