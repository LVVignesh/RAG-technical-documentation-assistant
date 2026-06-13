# RAG-Based Technical Documentation Assistant

A self-corrective **Retrieval-Augmented Generation (RAG)** system built with **LangGraph**, served through a **FastAPI** REST API. The system answers natural language questions about indexed technical documentation using an LLM-graded retrieval pipeline with automatic query rewriting.

---

## Project Overview

The assistant takes user questions about technical documentation, retrieves relevant chunks from a ChromaDB vector store, grades them for relevance, and generates grounded answers with citations. If no relevant documents are found, the pipeline automatically rewrites the query and retries (up to 3 times) before returning an "I don't know" response.

**Tech Stack**: Python 3.12 · LangGraph · LangChain · FastAPI · ChromaDB · FastEmbed · Groq (LLaMA 3.1 8B)

**Corpus**: 4 FastAPI documentation pages (intro, routing, dependency injection, query parameters)

---

## Architecture

### LangGraph Workflow

```
User Question
      │
      ▼
┌─────────────────┐
│  Query Analysis │  ← Rewrites & expands query; classifies query type
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Retrieval    │  ← ChromaDB similarity search (top-k=4 chunks)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Document Grading│  ← LLM grades each chunk as relevant/irrelevant
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
relevant?    no
    │         │
    │    retry_count < 3?
    │         │         │
    │        yes        no
    │         │         │
    │    back to       Generate "I don't know"
    │  Query Analysis
    ▼
┌─────────────────┐
│   Generation    │  ← LLM generates answer with citations
└─────────────────┘
```

### State Schema

| Field | Type | Description |
|-------|------|-------------|
| `question` | `str` | Original user question |
| `query` | `str` | Rewritten/expanded query for retrieval |
| `query_type` | `str` | `conceptual`, `how-to`, `troubleshooting`, `API reference` |
| `documents` | `List[Document]` | Raw retrieved chunks from vector store |
| `relevant_documents` | `List[Document]` | Filtered, graded-relevant chunks |
| `generation` | `str` | Final generated answer |
| `retry_count` | `int` | Number of query rewrite retries attempted |
| `max_retries` | `int` | Maximum allowed retries (default: 3) |

### Conditional Routing

After `Document Grading`:
- `relevant_documents` not empty → **Generate**
- `relevant_documents` empty AND `retry_count < max_retries` → **Query Analysis** (rewrite & retry)
- `relevant_documents` empty AND `retry_count >= max_retries` → **Generate** (returns "I don't know")

### Node Descriptions

1. **Query Analysis**: Uses Groq LLaMA 3.1 with structured output to rewrite the user's question into a richer search query and classify the query type (conceptual / how-to / troubleshooting / API reference). On retry, uses a broader/synonymous rewrite strategy.

2. **Retrieval**: Performs cosine similarity search against ChromaDB using FastEmbed embeddings (`BAAI/bge-small-en-v1.5`), returning the top-4 most similar chunks with source metadata.

3. **Document Grading**: Uses a plain LLM call asking for a binary "yes"/"no" relevance judgment for each chunk. Avoids structured output function calling (which Groq's API handles unreliably) in favor of direct text parsing.

4. **Generation**: Constructs a contextual prompt using only the relevant chunks (with source filenames) and generates a grounded, cited answer using Groq LLaMA 3.1.

---

## Setup Instructions

### 1. Clone and Navigate

```bash
git clone <your-repo-url>
cd RAG_assignment
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate   # Windows
source .venv/bin/activate  # macOS/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root (a template is provided in `.env.example`):

```env
GROQ_API_KEY=your_groq_api_key_here
LLM_MODEL=llama-3.1-8b-instant
DB_DIR=./chroma_db
```

Get a free Groq API key at: https://console.groq.com/

### 5. Run the Application

```bash
.\.venv\Scripts\uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

On startup, if the vector database is empty, the application automatically ingests the sample documents from `data/`.

---

## Quick Start Test

### Test via Swagger UI (Recommended)
1. Start the server: `.\.venv\Scripts\uvicorn main:app --reload`
2. Open: http://localhost:8000/docs
3. Click on `/query` endpoint → **Try it out**
4. Enter a test question and submit to see live responses

### Test via curl (Terminal)
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "How does dependency injection work in FastAPI?"}'
```

---

## API Reference

### Interactive Docs

Access the auto-generated Swagger UI at: `http://localhost:8000/docs`

### Endpoints

#### `POST /query` — Submit a question

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"question": "How does dependency injection work in FastAPI?"}'
```

**Response:**
```json
{
  "answer": "Dependency Injection in FastAPI allows you to declare dependencies...\n\n[fastapi_dependency_injection.md]",
  "sources": ["fastapi_dependency_injection.md"],
  "query_type": "how-to",
  "rewritten_query": "dependency injection in FastAPI example",
  "retry_count": 0
}
```

#### `POST /ingest` — Ingest a new document (file upload)

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "file=@./data/fastapi_intro.md"
```

**Response:**
```json
{"status": "success", "message": "Successfully indexed file: document.md"}
```

#### `POST /ingest` — Ingest a new document (URL)

```bash
curl -X POST "http://localhost:8000/ingest" \
  -F "url=https://fastapi.tiangolo.com/tutorial/dependencies/"
```

#### `GET /documents` — List indexed documents

```bash
curl "http://localhost:8000/documents"
```

**Response:**
```json
{
  "documents": [
    {"source": "./data/fastapi_intro.md", "filename": "fastapi_intro.md", "chunk_count": 5},
    {"source": "./data/fastapi_routing.md", "filename": "fastapi_routing.md", "chunk_count": 4}
  ]
}
```

#### `POST /feedback` — Submit feedback

```bash
curl -X POST "http://localhost:8000/feedback" \
  -H "Content-Type: application/json" \
  -d '{"rating": "thumbs_up", "comment": "Very helpful answer!"}'
```

**Response:**
```json
{"status": "success", "message": "Feedback submitted successfully."}
```

---

## Document Corpus

The sample corpus consists of 4 FastAPI official documentation pages in `data/`:

| File | Content |
|------|---------|
| `fastapi_intro.md` | FastAPI overview, key features, installation, basic example |
| `fastapi_routing.md` | Path operations, path parameters, data validation, routing order |
| `fastapi_dependency_injection.md` | Dependency injection concepts, `Depends()`, caching |
| `fastapi_query_params.md` | Query parameters, `Query` validation, min/max length, regex |

These documents were authored to cover the core FastAPI concepts and serve as a realistic technical documentation corpus for testing the RAG pipeline.

---

## Design Decisions & Tradeoffs

### LLM Provider: Groq (LLaMA 3.1 8B Instant)
**Why**: Free tier with fast inference. The 8B model is sufficient for query rewriting, grading, and generation on short technical docs.

**Tradeoff**: Groq's function-calling/tool-use API can fail with structured output for very short yes/no responses. The document grader was switched to a plain text "yes/no" prompt to avoid this.

### Embeddings: FastEmbed (`BAAI/bge-small-en-v1.5`)
**Why**: Runs fully locally, no API key required, small ONNX model (~130MB), fast inference, strong retrieval quality for English text.

**Tradeoff**: Slightly slower first run (downloads model weights on demand). No GPU acceleration on Windows without additional setup.

### Vector Store: ChromaDB
**Why**: Simple setup, persists to disk, runs locally. No infrastructure needed.

**Tradeoff**: Not suitable for production scale (millions of documents). FAISS or Pinecone would be better at scale.

### Chunking Strategy
**Parameters**: chunk_size=700, chunk_overlap=120

**Separators** (in priority order): `\n## `, `\n### `, `\n#### `, `\n\`\`\``, `\n\n`, `\n`, ` `

**Rationale**: Technical markdown is structured around headings and code blocks. Splitting on headers preserves conceptual coherence. The 700-char size fits within embedding model context limits while keeping code examples intact. 120-char overlap prevents splitting critical sentences at chunk boundaries.

### Self-Corrective Routing
The retry logic uses `retry_count` in state (incremented in `query_analysis`) with a hardcoded `max_retries=3`. The retry prompt is different from the initial one — it explicitly tells the LLM the previous attempt failed and asks for a broader/synonymous rewrite, which produces meaningfully different queries.

### Document Grading
Each retrieved chunk is graded independently by the LLM using a simple "yes/no" prompt. This allows partial relevance — if 3/4 retrieved chunks are relevant, only those 3 are passed to generation. This approach is more robust than "all or nothing" and avoids discarding partially useful context.

---

## What I Would Improve With More Time

1. **Hallucination check node**: Verify the generated answer is actually supported by the retrieved context (Self-RAG pattern) before returning it to the user.
2. **Web search fallback**: If `max_retries` is exhausted and still no relevant docs found, fall back to a web search (Tavily/Serper) before returning "I don't know."
3. **Conversation memory**: Maintain session-based chat history so follow-up questions have context (e.g., "What about its performance?" after asking about FastAPI features).
4. **Better error handling**: Return partial results or specific error codes when individual nodes fail.
5. **Metadata filtering**: Allow querying specific documents by source/filename via the API.
6. **Async workflow execution**: Make the LangGraph invocation async to prevent blocking FastAPI's event loop under concurrent load.
7. **Persistent feedback store**: Replace the JSON file with a SQLite/PostgreSQL table for production feedback storage.

---

## Running the Test Script

```bash
.\.venv\Scripts\python test_workflow.py
```

This runs 3 test queries and prints a full trace of each workflow step, showing the rewritten query, classified type, graded chunk counts, and final answer.
