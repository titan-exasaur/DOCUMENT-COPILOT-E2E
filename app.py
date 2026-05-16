import os, sys
import hashlib
from datetime import datetime

import boto3
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from src.ingestion import document_loader
from src.chunking import chunk_text
from src.embeddings import embedding_text
from src.opensearch_client import opensearch_client_maker
from src.indexing import create_index_if_not_exists, document_indexing
from src.retrieval import text_retrieval
from src.generation import llm_generation


# =========================
# ENV + CLIENTS
# =========================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

sys.path.append('src/')


# =========================
# AWS S3
# =========================

S3_BUCKET_NAME = "document-copilot-s3-bucket"

s3_client = boto3.client("s3")


# =========================
# STREAMLIT CONFIG
# =========================

st.set_page_config(
    page_title="Document Co-Pilot",
    layout="wide"
)

st.markdown(
    """
    <style>
        .main {
            background-color: #0e1117;
            color: white;
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .stTextInput > div > div > input {
            background-color: #1e1e1e;
            color: white;
        }

        .stTextInput label {
            color: white;
        }

        .stFileUploader label {
            color: white;
        }

        .title {
            font-size: 42px;
            font-weight: 800;
            background: linear-gradient(90deg, #00C6FF, #0072FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .subtext {
            color: #9aa4b2;
            margin-bottom: 2rem;
        }

        .card {
            background: #161b22;
            padding: 1rem;
            border-radius: 14px;
            border: 1px solid #2d333b;
            margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    "<div class='title'>📄 Document Co-Pilot</div>",
    unsafe_allow_html=True
)

st.markdown(
    "<div class='subtext'>Cloud-Native RAG Pipeline with OpenSearch + AWS + LLMs</div>",
    unsafe_allow_html=True
)


# =========================
# OPENSEARCH CLIENT
# =========================

@st.cache_resource
def get_client():
    return opensearch_client_maker()


opensearch_client = get_client()


# =========================
# SESSION STATE
# =========================

if "processed_pdf_hash" not in st.session_state:
    st.session_state.processed_pdf_hash = None

if "model" not in st.session_state:
    st.session_state.model = None

if "chunks" not in st.session_state:
    st.session_state.chunks = None

if "indexed" not in st.session_state:
    st.session_state.indexed = False

if "s3_file_key" not in st.session_state:
    st.session_state.s3_file_key = None


# =========================
# FILE UPLOAD
# =========================

pdf_file = st.file_uploader(
    "Upload PDF file",
    type=["pdf"]
)


# =========================
# MAIN FLOW
# =========================

if pdf_file is not None:

    # -----------------------------------------
    # HASH PDF CONTENT
    # -----------------------------------------

    pdf_bytes = pdf_file.getvalue()

    pdf_hash = hashlib.md5(pdf_bytes).hexdigest()

    # -----------------------------------------
    # CHECK IF NEW PDF
    # -----------------------------------------

    if st.session_state.processed_pdf_hash != pdf_hash:

        # =====================================
        # RESET INDEX TO AVOID CONTAMINATION
        # =====================================

        INDEX_NAME = "document-index"

        try:
            if opensearch_client.indices.exists(index=INDEX_NAME):
                opensearch_client.indices.delete(index=INDEX_NAME)

        except Exception as e:
            st.error(f"Index cleanup failed: {e}")

        # =====================================
        # UPLOAD TO S3
        # =====================================

        upload_time = datetime.now().strftime("%Y%m%d_%H%M%S")

        s3_filename = f"{upload_time}_{pdf_file.name}"

        try:

            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_filename,
                Body=pdf_bytes
            )

            st.success(f"PDF uploaded to S3: {s3_filename}")

            st.session_state.s3_file_key = s3_filename

        except Exception as e:
            st.error(f"S3 Upload Failed: {e}")

        # =====================================
        # DOCUMENT LOADING
        # =====================================

        with st.spinner("Loading PDF..."):

            pdf_text = document_loader(pdf_file)

        st.success("PDF loaded successfully")

        # =====================================
        # CHUNKING
        # =====================================

        with st.spinner("Chunking document..."):

            texts = [doc["text"] for doc in pdf_text]

            chunks = chunk_text(texts)

        st.info(f"Total Chunks: {len(chunks)}")

        # =====================================
        # EMBEDDINGS
        # =====================================

        with st.spinner("Generating embeddings..."):

            model, embeddings = embedding_text(chunks)

        st.info(f"Total Embeddings: {len(embeddings)}")

        # =====================================
        # INDEXING
        # =====================================

        with st.spinner("Indexing into OpenSearch..."):

            create_index_if_not_exists(opensearch_client)

            document_indexing(
                chunks=chunks,
                embeddings=embeddings,
                client=opensearch_client
            )

        st.success("Indexing complete")

        # =====================================
        # CACHE SESSION
        # =====================================

        st.session_state.processed_pdf_hash = pdf_hash

        st.session_state.model = model

        st.session_state.chunks = chunks

        st.session_state.indexed = True

    else:

        st.success("Using cached embeddings and OpenSearch index")

        model = st.session_state.model

        chunks = st.session_state.chunks

    # =========================================
    # QUERY SECTION
    # =========================================

    st.divider()

    st.markdown("## 🔍 Ask Your Document")

    query = st.text_input(
        "Enter your query"
    )

    if query:

        # =====================================
        # QUERY EMBEDDING
        # =====================================

        with st.spinner("Embedding query..."):

            query_embedding = model.encode(query)

        # =====================================
        # RETRIEVAL
        # =====================================

        with st.spinner("Retrieving relevant chunks..."):

            retrieved_text = text_retrieval(
                opensearch_client,
                query_embedding,
                k=5
            )

        # =====================================
        # LLM GENERATION
        # =====================================

        with st.spinner("Generating answer using LLM..."):

            rag_text = llm_generation(
                query=query,
                context=retrieved_text,
                llm_client=openai_client
            )

        # =====================================
        # DISPLAY ANSWER
        # =====================================

        st.markdown("## 🧾 Answer")

        st.success(rag_text)

    else:

        st.warning("Write a query")

else:

    st.info("Upload a PDF to begin analysis")