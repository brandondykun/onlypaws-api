#!/bin/bash
# Downloads the CLIP embedding model to a host directory (models/)
# so it can be volume-mounted into containers instead of baked into the image.
#
# Usage: ./scripts/download_model.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MODEL_DIR="$PROJECT_DIR/models"

mkdir -p "$MODEL_DIR"

echo "Downloading sentence-transformers/clip-ViT-B-32 into $MODEL_DIR ..."

docker run --rm \
  -v "$MODEL_DIR:/models" \
  -e SENTENCE_TRANSFORMERS_HOME=/models \
  -e HF_HOME=/models \
  python:3.12.2-slim \
  bash -c '
    pip install --quiet sentence-transformers pillow &&
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer(\"sentence-transformers/clip-ViT-B-32\")"
  '

echo "Model downloaded to $MODEL_DIR"
