import os
import re
import requests
from typing import List, Dict, Any
from urllib.parse import urlparse
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings

# Define paths
DB_DIR = os.getenv("DB_DIR", "./chroma_db")

def get_vector_store():
    """Initializes and returns the Chroma vector store."""
    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    return Chroma(
        collection_name="tech_docs",
        embedding_function=embeddings,
        persist_directory=DB_DIR
    )

def extract_text_from_html(html_content: str) -> str:
    """Extracts plain text from HTML, removing scripts, styles, and tags."""
    # Basic clean up of script and style blocks
    clean_content = re.sub(r'<(script|style).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    # Remove all HTML tags
    clean_content = re.sub(r'<.*?>', ' ', clean_content)
    # Decode HTML entities
    import html
    clean_content = html.unescape(clean_content)
    # Normalize whitespaces
    clean_content = re.sub(r'\s+', ' ', clean_content).strip()
    return clean_content

def load_document(source: str) -> str:
    """Loads content from a local file path or a URL."""
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        # URL source
        response = requests.get(source, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type:
            return extract_text_from_html(response.text)
        return response.text
    else:
        # File source
        if not os.path.exists(source):
            raise FileNotFoundError(f"File not found: {source}")
        
        _, ext = os.path.splitext(source.lower())
        with open(source, "r", encoding="utf-8") as f:
            content = f.read()
            
        if ext == ".html":
            return extract_text_from_html(content)
        return content

def split_document(content: str, source: str) -> List[Document]:
    """Splits document content into chunks using RecursiveCharacterTextSplitter."""
    # Using separators tailored for technical content (markdown headers, code blocks, lists)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=700,
        chunk_overlap=120,
        separators=["\n## ", "\n### ", "\n#### ", "\n```", "\n\n", "\n", " ", ""]
    )
    
    # Generate metadata
    metadata = {
        "source": source,
        "filename": os.path.basename(source) if not source.startswith("http") else source
    }
    
    chunks = splitter.split_text(content)
    return [Document(page_content=chunk, metadata=metadata) for chunk in chunks]

def ingest_document(source: str) -> List[Document]:
    """Loads, splits, and indexes a document from file or URL."""
    content = load_document(source)
    documents = split_document(content, source)
    
    vector_store = get_vector_store()
    vector_store.add_documents(documents)
    return documents

def list_indexed_documents() -> List[Dict[str, Any]]:
    """Retrieves unique list of indexed documents in the vector store."""
    vector_store = get_vector_store()
    try:
        data = vector_store.get()
        metadatas = data.get("metadatas", [])
        
        # Track unique documents by their source
        unique_docs = {}
        for m in metadatas:
            if not m or "source" not in m:
                continue
            source = m["source"]
            if source not in unique_docs:
                unique_docs[source] = {
                    "source": source,
                    "filename": m.get("filename", os.path.basename(source)),
                    "chunk_count": 0
                }
            unique_docs[source]["chunk_count"] += 1
            
        return list(unique_docs.values())
    except Exception:
        # If DB is not initialized yet, return empty list
        return []
