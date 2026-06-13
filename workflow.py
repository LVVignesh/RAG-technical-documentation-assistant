import os
from typing import List, Dict, Any, TypedDict
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from ingestion import get_vector_store

# Initialize ChatGroq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

llm = ChatGroq(
    groq_api_key=GROQ_API_KEY,
    model_name=LLM_MODEL,
    temperature=0
)

# -----------------
# 1. State Schema
# -----------------
class AgentState(TypedDict):
    question: str
    query: str
    query_type: str
    documents: List[Document]
    relevant_documents: List[Document]
    generation: str
    retry_count: int
    max_retries: int

# -----------------
# 2. Pydantic Models for Structured Output
# -----------------
from pydantic import BaseModel, Field

class QueryAnalysisOutput(BaseModel):
    rewritten_query: str = Field(description="The optimized search query for similarity search. Add synonyms and expand the query.")
    query_type: str = Field(description="The classified type of query: conceptual, how-to, troubleshooting, API reference.")

# -----------------
# 3. Nodes
# -----------------

def query_analysis(state: AgentState) -> Dict[str, Any]:
    """Analyzes the user's question, expands it, and classifies the type."""
    question = state["question"]
    retry_count = state.get("retry_count", 0)
    
    # Structure output
    structured_llm = llm.with_structured_output(QueryAnalysisOutput)
    
    if retry_count > 0:
        system_prompt = (
            "You are an expert AI search optimizer. The previous query rewrite did not yield relevant results.\n"
            "Analyze the user question and rewrite it to be broader or use different synonyms to locate relevant technical documentation."
        )
    else:
        system_prompt = (
            "You are an expert AI search optimizer. Analyze the user question and prepare it for retrieval.\n"
            "1. Rewrite or expand the query to improve retrieval quality (add synonyms, clarify terms, specify context).\n"
            "2. Classify the query type as conceptual, how-to, troubleshooting, or API reference."
        )
        
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "User Question: {question}")
    ])
    
    chain = prompt | structured_llm
    result = chain.invoke({"question": question})
    
    rewritten = result.rewritten_query.strip() if result.rewritten_query else question
    
    return {
        "query": rewritten,
        "query_type": result.query_type,
        "retry_count": retry_count + 1
    }

def retrieve(state: AgentState) -> Dict[str, Any]:
    """Retrieves documents from vector store using the rewritten query."""
    query = state["query"]
    
    vector_store = get_vector_store()
    docs = vector_store.similarity_search(query, k=4)
    
    return {"documents": docs}

def grade_documents(state: AgentState) -> Dict[str, Any]:
    """Grades retrieved documents. Filters out irrelevant ones."""
    question = state["question"]
    documents = state["documents"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a grader assessing relevance of a retrieved document to a user question.\n"
                "If the document contains keyword(s) or semantic meaning related to the user question, respond with 'yes'.\n"
                "Otherwise respond with 'no'.\n"
                "Respond with ONLY the single word 'yes' or 'no', nothing else."),
        ("human", "Retrieved Document:\n\n{document}\n\nUser Question: {question}\n\nIs this document relevant? Answer yes or no:")
    ])
    
    chain = prompt | llm
    
    relevant_docs = []
    for doc in documents:
        try:
            result = chain.invoke({"document": doc.page_content, "question": question})
            answer = result.content.strip().lower()
            if "yes" in answer:
                relevant_docs.append(doc)
        except Exception:
            # If grading fails for a doc, skip it (treat as irrelevant)
            pass
            
    return {"relevant_documents": relevant_docs}

def generate(state: AgentState) -> Dict[str, Any]:
    """Generates an answer based on the graded relevant documents."""
    question = state["question"]
    relevant_docs = state["relevant_documents"]
    
    if not relevant_docs:
        generation = (
            "I'm sorry, but I couldn't find any relevant information in the technical documentation to answer your question.\n"
            "Please try rephrasing your question or asking about a different topic."
        )
        return {"generation": generation}
        
    context_parts = []
    for doc in relevant_docs:
        filename = doc.metadata.get("filename", "unknown source")
        context_parts.append(f"Source: [{filename}]\nContent:\n{doc.page_content}\n---")
    context = "\n".join(context_parts)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert technical documentation assistant. Answer the user's question using ONLY the provided context.\n"
                "Ground your answer fully in the context. Format your response with citations referencing the source document name (e.g. `[fastapi_intro.md]`).\n"
                "If the context is insufficient or if you don't know the answer, state clearly that you don't know.\n"
                "Do not make up an answer or use external information outside the context."),
        ("human", "Context:\n{context}\n\nQuestion: {question}")
    ])
    
    chain = prompt | llm
    result = chain.invoke({"context": context, "question": question})
    
    return {"generation": result.content}

# -----------------
# 4. Routing Logic (Conditional Edges)
# -----------------
def decide_to_generate(state: AgentState) -> str:
    """Routes the workflow based on document grading results and retry count."""
    relevant_docs = state["relevant_documents"]
    retry_count = state["retry_count"]
    max_retries = state.get("max_retries", 3)
    
    if relevant_docs:
        return "generate"
    elif retry_count < max_retries:
        return "rewrite"
    else:
        return "generate"

# -----------------
# 5. Build Graph
# -----------------
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("query_analysis", query_analysis)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("generate", generate)

# Set Entry Point
workflow.set_entry_point("query_analysis")

# Define Transitions
workflow.add_edge("query_analysis", "retrieve")
workflow.add_edge("retrieve", "grade_documents")

# Add Conditional Edges
workflow.add_conditional_edges(
    "grade_documents",
    decide_to_generate,
    {
        "generate": "generate",
        "rewrite": "query_analysis"
    }
)

workflow.add_edge("generate", END)

# Compile the graph
graph = workflow.compile()
