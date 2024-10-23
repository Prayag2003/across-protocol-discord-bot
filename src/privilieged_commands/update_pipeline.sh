#!/bin/bash

# Exit on any error
set -e

set -x  # Enable tracing

echo "Starting pipeline execution..."

# Run scraper
echo "Running scraper..."
python scraper/scraper.py
echo "✅ Scraper completed"

# Create knowledge base
echo "Creating knowledge base..."
python scraper/create_knowledge_base_from_json.py
echo "✅ Knowledge base created"

# Generate embeddings
echo "Generating embeddings..."
python knowledge_base/generate_embeddings.py
echo "✅ Embeddings generated"

# Merge embeddings
echo "Merging embeddings..."
python knowledge_base/merge_embeddings.py
echo "✅ Embeddings merged"

echo "✅ Inference setup completed..."

echo "Pipeline completed successfully!"