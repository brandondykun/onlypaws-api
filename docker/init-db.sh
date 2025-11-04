#!/bin/bash
set -e

# This script runs automatically when the PostgreSQL container initializes
# It creates the pgvector extension in the database

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
EOSQL

echo "pgvector extension created successfully"

