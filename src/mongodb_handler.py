import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient


# =========================
# LOAD ENV VARIABLES
# =========================

load_dotenv()

MONGO_URI = os.getenv("MONGO_CONNECTION_URI")


# =========================
# CONNECT TO MONGODB ATLAS
# =========================

client = MongoClient(MONGO_URI)

db = client["document_copilot_db"]

collection = db["rag_metadata"]


# =========================
# STORE METADATA FUNCTION
# =========================

def store_metadata(
    pdf_name,
    query,
    response,
    document_processing_time,
    document_embedding_time,
    chunk_count,
    embedding_count,
    indexing_time,
    retrieval_time,
    retrieved_chunks_count,
    llm_response_time,
    total_time,
    status
):

    metadata = {

        "pdf_name": pdf_name,
        "query": query,
        "response": response,
        "document_processing_time_seconds": document_processing_time,
        "document_embedding_time_seconds": document_embedding_time,
        "chunk_count": chunk_count,
        "embedding_count": embedding_count,
        "indexing_time": indexing_time,
        "retrieval_time_seconds": retrieval_time,
        "retrieved_chunks_count": retrieved_chunks_count,
        "llm_response_time_seconds": llm_response_time,
        "total_pipeline_time_seconds": total_time,
        "status": status,
        "timestamp": datetime.now(timezone.utc)

    }

    result = collection.insert_one(metadata)

    return result.inserted_id