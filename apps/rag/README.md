# RAG Document Ingestion

Python services for document chunking, embedding generation, and vector storage.

## Components

### 1. Document Chunker (`chunker.py`)
Splits documents into semantic chunks using LangChain.

**Features**:
- Recursive character splitting (512 chars, 50 overlap)
- Generates unique document IDs (SHA256 hash)
- Preserves metadata (title, doc_type, tenant_id, version)

### 2. OpenAI Embedder (`embedder.py`)
Generates vector embeddings using OpenAI API.

**Model**: `text-embedding-3-small` (1536 dimensions)

**Features**:
- Batch processing (100 chunks per API call)
- Rate limiting (0.1s delay between batches)
- Query embedding for similarity search

### 3. Document Ingester (`ingest.py`)
End-to-end ingestion pipeline.

**Workflow**:
1. Read document file
2. Check for duplicates (SHA256 hash)
3. Chunk document (512-char chunks)
4. Generate OpenAI embeddings
5. Insert into pgvector database
6. Vector similarity search support

## Usage

### Ingest a Document

```bash
python apps/rag/ingest.py \
  --file docs/manuals/haas-vf2-cnc-manual.md \
  --title "Haas VF-2 CNC Machine Manual" \
  --doc-type manual \
  --tenant-id acme-manufacturing \
  --version "2.0" \
  --db-host localhost \
  --db-port 5432
```

**Prerequisites**:
- Port-forward Postgres: `kubectl port-forward -n postgres svc/postgres 5432:5432`
- Set OpenAI API key: `export OPENAI_API_KEY=sk-...`

### Test Similarity Search

```bash
# Install dependencies
pip install -r apps/rag/requirements.txt

# Run search test
python apps/rag/test_search.py
```

**Example queries**:
- "How to fix high vibration on CNC machine?"
- "What causes tool temperature to rise?"
- "CNC machine maintenance schedule"

## Database Schema

### `document_embeddings` Table
| Column | Type | Description |
|--------|------|-------------|
| id | BIGSERIAL | Primary key |
| document_id | VARCHAR(255) | Unique document ID (hash) |
| tenant_id | VARCHAR(100) | Customer ID (multi-tenancy) |
| chunk_index | INTEGER | Chunk position in document |
| doc_type | VARCHAR(50) | `manual`, `runbook`, `kb_article`, `ADR` |
| title | TEXT | Document title |
| content | TEXT | Chunk text content |
| embedding | vector(1536) | OpenAI embedding |

**Indexes**:
- HNSW index on `embedding` (fast cosine similarity)
- B-tree indexes on `tenant_id`, `doc_type`, `document_id`

### `documents` Table
Metadata and deduplication tracking.

| Column | Type | Description |
|--------|------|-------------|
| document_id | VARCHAR(255) | Unique ID |
| file_hash | VARCHAR(64) | SHA256 hash (deduplication) |
| chunk_count | INTEGER | Number of chunks |
| embedding_model | VARCHAR(100) | Model used (`text-embedding-3-small`) |

## Cost Estimate

**OpenAI Pricing**: $0.02 per 1M tokens

**Example** (100 device manuals):
- 100 manuals × 50 pages × 500 tokens/page = 2.5M tokens
- **One-time ingestion**: $0.05
- **Monthly updates** (10 docs): $0.005/month

## Dependencies

```
openai==1.12.0
langchain==0.1.0
psycopg2-binary==2.9.9
pypdf==4.0.0         # For PDF parsing (future)
python-magic==0.4.27  # For file type detection
pyyaml==6.0
```

## Development

### Add New Document Type

```python
# In ingest.py, add to doc_type choices:
parser.add_argument('--doc-type', choices=[
    'manual', 'runbook', 'kb_article', 'ADR', 'sop'  # Add new type
])
```

### Customize Chunking

```python
from rag.chunker import DocumentChunker

# Create custom chunker
chunker = DocumentChunker(
    chunk_size=1024,  # Larger chunks
    chunk_overlap=100  # More overlap
)
```

### Query with Filters

```python
results = ingester.search_similar(
    query="high vibration troubleshooting",
    tenant_id="acme-manufacturing",  # Filter by customer
    doc_type="manual",                # Filter by type
    top_k=10                          # More results
)
```

## Troubleshooting

### OpenAI API Key Not Found
```bash
export OPENAI_API_KEY=sk-your-key-here
```

### Database Connection Failed
```bash
# Verify port-forward is running
kubectl port-forward -n postgres svc/postgres 5432:5432

# Test connection
psql -h localhost -p 5432 -U postgres -d iot_ops
```

### pgvector Extension Missing
```sql
-- Enable extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
```

## Next Steps

1. **Airflow DAG**: Automate document ingestion on schedule
2. **Hybrid Search**: Combine vector + BM25 for better results
3. **Reranking**: Add cross-encoder reranking layer
4. **PDF Support**: Extract text from PDF manuals
5. **Metadata Enrichment**: Parse structured sections (errors, specs)
