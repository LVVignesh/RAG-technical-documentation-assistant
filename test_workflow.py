import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Verify GROQ_API_KEY
if not os.getenv("GROQ_API_KEY"):
    print("Error: GROQ_API_KEY is not set. Please check your .env file.")
    sys.exit(1)

from ingestion import ingest_document, list_indexed_documents
from workflow import graph

def run_test_query(question: str):
    print("=" * 60)
    print(f"QUESTION: {question}")
    print("=" * 60)
    
    initial_state = {
        "question": question,
        "retry_count": 0,
        "max_retries": 3,
        "documents": [],
        "relevant_documents": [],
        "query": "",
        "query_type": "",
        "generation": ""
    }
    
    # Run the workflow
    # We can stream intermediate steps to see self-correction in action
    try:
        print("Running LangGraph workflow...")
        state = initial_state
        for event in graph.stream(state):
            for node_name, node_state in event.items():
                print(f"\n--- Node: {node_name} completed ---")
                if "query" in node_state and node_state["query"]:
                    print(f"  Rewritten Query: '{node_state['query']}'")
                if "query_type" in node_state and node_state["query_type"]:
                    print(f"  Classified Query Type: {node_state['query_type']}")
                if "documents" in node_state:
                    print(f"  Retrieved {len(node_state['documents'])} chunks")
                if "relevant_documents" in node_state:
                    print(f"  Graded {len(node_state['relevant_documents'])} chunks as relevant")
                if "retry_count" in node_state:
                    print(f"  Retry Count: {node_state['retry_count']}")
                state.update(node_state)
        
        print("\n" + "=" * 60)
        print("FINAL ANSWER:")
        print("=" * 60)
        print(state.get("generation"))
        print("\nSources used:")
        sources = list(set([
            doc.metadata.get("filename", os.path.basename(doc.metadata.get("source", "unknown")))
            for doc in state.get("relevant_documents", [])
        ]))
        print(sources if sources else "None")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"Error executing workflow: {e}")

def main():
    print("Checking indexed documents...")
    docs = list_indexed_documents()
    if not docs:
        print("Vector database is empty. Ingesting sample documents from data/...")
        sample_dir = "./data"
        if os.path.exists(sample_dir):
            for filename in os.listdir(sample_dir):
                if filename.endswith(".md"):
                    file_path = os.path.join(sample_dir, filename)
                    print(f"Ingesting {filename}...")
                    ingest_document(file_path)
            print("Ingestion complete.")
        else:
            print("Error: data/ directory not found.")
            sys.exit(1)
    else:
        print(f"Found {len(docs)} indexed documents: {[d['filename'] for d in docs]}")

    # Test Case 1: Standard RAG (should find info in fastapi_intro.md or routing.md)
    run_test_query("What are the key features of FastAPI and how do I install it?")

    # Test Case 2: Standard RAG (should find info in dependency_injection.md)
    run_test_query("How does dependency injection work in FastAPI? Explain with an example.")

    # Test Case 3: Self-correction / Retry Limit (should fail retrieval, rewrite query, retry, and eventually answer 'I don't know')
    run_test_query("How do I build a rocket using python fastapi?")

if __name__ == "__main__":
    main()
