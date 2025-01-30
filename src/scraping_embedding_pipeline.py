import os
from scraper_v2.scraper import Scraper
from embedding.embedder import Embedder

with open("redundant_data.txt", "r", encoding="utf-8") as file:
    redundant_data = file.read()

# Create directories if they do not exist
directories = [
    "scraped_data/v3",
    "scraped_data/v2",
    "scraped_data/user_docs"
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)

# Scrape and save JSON files
scrapers = [
    {"BASE_URL": "https://docs.across.to/", "OUTPUT_FILE": "scraped_data/v3/processed_data_v3.json"},
    {"BASE_URL": "https://docs.across.to/developer-docs", "OUTPUT_FILE": "scraped_data/v2/processed_data_v2.json"},
    {"BASE_URL": "https://docs.across.to/user-docs/", "OUTPUT_FILE": "scraped_data/user_docs/processed_data_user_docs.json"}
]

for scraper_info in scrapers:
    scraper = Scraper(scraper_info["BASE_URL"], scraper_info["OUTPUT_FILE"], redundant_data)
    scraper.run(depth=2)

# Now create embeddings from the scraped JSON files
processed_files = [
    "scraped_data/v3/processed_data_v3.json",
    "scraped_data/v2/processed_data_v2.json",
    "scraped_data/user_docs/processed_data_user_docs.json"
]

output_directory = "vector_store"

embedder = Embedder(output_directory)
embedder.create_embeddings(processed_files)
