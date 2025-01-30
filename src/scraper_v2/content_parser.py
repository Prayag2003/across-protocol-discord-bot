from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from loguru import logger

class ContentParser:
    def __init__(self, redundant_data):
        self.redundant_data = redundant_data
        self.redundant_data_list = [line.strip() for line in redundant_data.split('\n') if line.strip()]

    def extract_content(self, html_content):
        """Extract meaningful content from HTML."""
        soup = BeautifulSoup(html_content, 'html.parser')

        info = {
            "title": soup.title.string if soup.title else "No title",
            "headers": [header.get_text() for header in soup.find_all(['h1', 'h2', 'h3'])],
            "paragraphs": [para.get_text() for para in soup.find_all('p')],
            "lists": [ul.get_text(separator='\n').strip() for ul in soup.find_all('ul')],
            "tables": [],
            "code_blocks": [],
        }

        # Remove redundant data
        info["headers"] = [header for header in info["headers"] if not any(redundant in header for redundant in self.redundant_data_list)]
        info["paragraphs"] = [para for para in info["paragraphs"] if not any(redundant in para for redundant in self.redundant_data_list)]
        info["lists"] = [ul for ul in info["lists"] if not any(redundant in ul for redundant in self.redundant_data_list)]

        # Extract tables
        for table in soup.find_all('table'):
            table_data = []
            for row in table.find_all('tr'):
                row_data = [cell.get_text().strip() for cell in row.find_all(['td', 'th'])]
                table_data.append(row_data)
            info["tables"].append(table_data)

        # Extract code blocks
        for code in soup.find_all('code', id=True):
            info["code_blocks"].append({
                "id": code['id'],
                "code": code.get_text().strip()
            })

        return info

    def extract_links(self, html_content, base_url):
        """Extract and return all links from the page."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        for a_tag in soup.find_all('a', href=True):
            link = a_tag.get('href')
            if link:
                full_link = urljoin(base_url, link) if not urlparse(link).netloc else link
                links.append(full_link)
        logger.info(f"Found {len(links)} links for {base_url}")
        return links
