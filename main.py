import os
import json
from datetime import datetime
from typing import Optional, Literal, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from ingestion import ingest_document, list_indexed_documents
from workflow import graph

app = FastAPI(
    title="RAG-Based Technical Documentation Assistant",
    description="FastAPI application serving a LangGraph-powered self-corrective RAG system.",
    version="1.0.0"
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# File for storing user feedback
FEEDBACK_FILE = "./feedback.json"

# -----------------
# Pydantic Schemas
# -----------------
class QueryRequest(BaseModel):
    question: str = Field(..., description="The user's question about the technical documentation.")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated answer, grounded in retrieved documents.")
    sources: List[str] = Field(..., description="List of source filenames or URLs used for the answer.")
    query_type: str = Field(..., description="The classified category of the query.")
    rewritten_query: str = Field(..., description="The query used for final retrieval.")
    retry_count: int = Field(..., description="The number of self-corrective retries attempted.")

class FeedbackRequest(BaseModel):
    rating: Literal["thumbs_up", "thumbs_down"] = Field(..., description="Feedback rating.")
    comment: Optional[str] = Field(None, description="Optional text feedback or comments.")

# -----------------
# Endpoints
# -----------------

@app.get("/")
async def read_root():
    return RedirectResponse(url="/docs")

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Submits a question to the assistant.
    The system runs a self-corrective LangGraph workflow that rewrites queries
    and filters documents for relevance before generating an answer.
    """
    try:
        # Run workflow
        initial_state = {
            "question": request.question,
            "retry_count": 0,
            "max_retries": 3,
            "documents": [],
            "relevant_documents": [],
            "query": "",
            "query_type": "",
            "generation": ""
        }
        
        result = graph.invoke(initial_state)
        
        # Extract sources from relevant documents
        sources = list(set([
            doc.metadata.get("filename", os.path.basename(doc.metadata.get("source", "unknown")))
            for doc in result.get("relevant_documents", [])
        ]))
        
        return QueryResponse(
            answer=result.get("generation", ""),
            sources=sources,
            query_type=result.get("query_type", "unknown"),
            rewritten_query=result.get("query", ""),
            retry_count=result.get("retry_count", 1) - 1 # Adjusted to get actual retries count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.post("/ingest")
async def ingest_endpoint(
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None)
):
    """
    Ingests new documents.
    Accepts file uploads (Markdown, text, or HTML) or a URL to fetch content.
    """
    if not file and not url:
        raise HTTPException(status_code=400, detail="Must provide either a file upload or a URL.")
        
    try:
        if file:
            os.makedirs("./uploaded_docs", exist_ok=True)
            file_path = os.path.join("./uploaded_docs", file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
            
            ingest_document(file_path)
            return {"status": "success", "message": f"Successfully indexed file: {file.filename}"}
            
        elif url:
            ingest_document(url)
            return {"status": "success", "message": f"Successfully indexed URL: {url}"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error ingesting document: {str(e)}")

@app.get("/documents")
async def list_documents_endpoint():
    """
    Lists all indexed documents currently in the corpus.
    """
    try:
        docs = list_indexed_documents()
        return {"documents": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@app.post("/feedback")
async def feedback_endpoint(request: FeedbackRequest):
    """
    Submits user feedback (thumbs up/down + optional comment) on generated answers.
    Feedback is stored locally in feedback.json.
    """
    try:
        feedback_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "rating": request.rating,
            "comment": request.comment
        }
        
        # Load existing feedback
        existing_feedback = []
        if os.path.exists(FEEDBACK_FILE):
            try:
                with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                    existing_feedback = json.load(f)
            except Exception:
                existing_feedback = []
                
        existing_feedback.append(feedback_entry)
        
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_feedback, f, indent=4, ensure_ascii=False)
            
        return {"status": "success", "message": "Feedback submitted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving feedback: {str(e)}")

# -----------------
# Startup Events
# -----------------
@app.on_event("startup")
async def startup_event():
    """
    On startup, check if the vector database is empty.
    If empty, automatically ingest sample files from the data/ directory.
    """
    try:
        docs = list_indexed_documents()
        if not docs:
            print("Vector database is empty. Ingesting sample files from data/...")
            sample_dir = "./data"
            if os.path.exists(sample_dir):
                for filename in os.listdir(sample_dir):
                    if filename.endswith(".md") or filename.endswith(".txt") or filename.endswith(".html"):
                        file_path = os.path.join(sample_dir, filename)
                        try:
                            ingest_document(file_path)
                            print(f"Ingested sample document: {filename}")
                        except Exception as e:
                            print(f"Failed to ingest {filename}: {e}")
            else:
                print("Sample data directory does not exist.")
    except Exception as e:
        print(f"Error checking/initializing database on startup: {e}")
