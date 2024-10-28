#!/bin/bash

set -e
set -x

echo "Starting pipeline execution..."

echo "Running scraper..."
python scraper/scraper.py
echo "✅ Scraper completed"

echo "Creating knowledge base..."
python scraper/create_knowledge_base_from_json.py
echo "✅ Knowledge base created"

echo "Generating embeddings..."
python knowledge_base/generate_embeddings.py
echo "✅ Embeddings generated"

echo "Merging embeddings..."
python knowledge_base/merge_embeddings.py
echo "✅ Embeddings merged"

echo "✅ Inference setup completed..."

echo "Pipeline completed successfully!"