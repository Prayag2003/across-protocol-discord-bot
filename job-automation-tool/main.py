import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from tabulate import tabulate

# ----------------------------------------
# Logging configuration
# ----------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ----------------------------------------
# Headless Chrome setup
# ----------------------------------------
logger.info("Launching headless Chrome browser...")
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

url = "https://getfluently.notion.site/Y-Combinator-Startup-Jobs-1ec6a9ce04d980368a1ac59e3503a531"
try:
    logger.info(f"Opening URL: {url}")
    driver.get(url)
    time.sleep(7)  # Allow JS to load

    soup = BeautifulSoup(driver.page_source, "html.parser")
    logger.info("Page loaded. Parsing content...")

    job_data = []
    last_company = None

    for block in soup.find_all("div"):
        text = block.get_text(strip=True)

        # Detect company section
        if text.isupper() and len(text.split()) <= 3:
            last_company = text

        # Detect apply/contact links
        for a in block.find_all("a", href=True):
            link_text = a.get_text(strip=True)
            href = a["href"]
            if "apply" in link_text.lower() or "careers" in link_text.lower() or "mailto:" in href or "http" in href:
                job_data.append({
                    "Company": last_company,
                    "Text": link_text,
                    "Link": href
                })

    logger.info(f"Total entries collected: {len(job_data)}")

    # Export to .txt
    with open("yc_jobs.txt", "w", encoding="utf-8") as f:
        for item in job_data:
            f.write(f"{item['Company']} | {item['Text']} | {item['Link']}\n")

    # Print in table format
    print("\n" + tabulate(job_data, headers="keys", tablefmt="grid"))

except Exception as e:
    logger.error(f"Error occurred: {e}")

finally:
    logger.info("Shutting down browser...")
    driver.quit()
