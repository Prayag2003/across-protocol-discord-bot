import os
import json
import shutil
import requests
from urllib.parse import urljoin, urlparse
from loguru import logger
from scraper_v2.content_parser import ContentParser

class Scraper:
    def __init__(self, base_url, output_file, redundant_data):
        self.base_url = base_url
        self.output_file = output_file
        self.redundant_data = redundant_data
        self.visited = set()

    def scrape_page(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        else:
            logger.error(f"Failed to retrieve {url}: {response.status_code}")
            return None

    def crawl_and_extract(self, url, depth=1):
        """Crawl and extract content recursively from a website."""
        if depth == 0 or url in self.visited:
            return {}

        self.visited.add(url)
        logger.info(f"Crawling: {url}")

        html_content = self.scrape_page(url)
        if not html_content:
            return {}

        # Parse content using ContentParser
        content_parser = ContentParser(self.redundant_data)
        processed_data = {url: content_parser.extract_content(html_content)}

        # Find and follow links
        links = content_parser.extract_links(html_content, url)
        for link in links:
            processed_data.update(self.crawl_and_extract(link, depth=depth - 1))

        return processed_data

    def save_data(self, data):
        """Save scraped data to a JSON file."""
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        temp_file = f"{self.output_file}.tmp"
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        shutil.move(temp_file, self.output_file)
        logger.info(f"Data saved to {self.output_file}")

    def run(self, depth=2):
        """Run the scraping and extraction process."""
        logger.info(f"Starting scraping for {self.base_url}...")
        processed_data = self.crawl_and_extract(self.base_url, depth)
        self.save_data(processed_data)
