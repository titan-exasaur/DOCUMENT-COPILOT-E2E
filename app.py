import os
import sys
import hashlib
import time
from datetime import datetime

import boto3
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

from src.opensearch_client import opensearch_client_maker
from src.retrieval import text_retrieval
from src.generation import llm_generation
from src.mongodb_handler import store_metadata
from src.query_embedding import embed_query


# =========================================================
# ENV + CLIENTS
# =========================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)

sys.path.append("src/")


# =========================================================
# AWS S3
# =========================================================

S3_BUCKET_NAME = "document-copilot-s3-bucket"

s3_client = boto3.client("s3")


# =========================================================
# STREAMLIT CONFIG
# =========================================================

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


# =========================================================
# OPENSEARCH CLIENT
# =========================================================

@st.cache_resource
def get_client():
    return opensearch_client_maker()


opensearch_client = get_client()


# =========================================================
# SESSION STATE
# =========================================================

if "processed_pdf_hash" not in st.session_state:
    st.session_state.processed_pdf_hash = None

if "s3_file_key" not in st.session_state:
    st.session_state.s3_file_key = None


# =========================================================
# FILE UPLOAD
# =========================================================

pdf_file = st.file_uploader(
    "Upload PDF file",
    type=["pdf"]
)


# =========================================================
# MAIN FLOW
# =========================================================

if pdf_file is not None:

    total_pipeline_start = time.time()

    # -----------------------------------------------------
    # HASH PDF
    # -----------------------------------------------------

    pdf_bytes = pdf_file.getvalue()

    pdf_hash = hashlib.md5(
        pdf_bytes
    ).hexdigest()

    # -----------------------------------------------------
    # CHECK IF NEW PDF
    # -----------------------------------------------------

    if st.session_state.processed_pdf_hash != pdf_hash:

        upload_time = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        s3_filename = (
            f"{upload_time}_{pdf_file.name}"
        )

        # -------------------------------------------------
        # UPLOAD TO S3
        # -------------------------------------------------

        try:

            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=s3_filename,
                Body=pdf_bytes,
                ContentType="application/pdf",
                Metadata={
                    "doc_hash": pdf_hash,
                    "upload_time": upload_time
                }
            )

            st.success(
                f"PDF uploaded to S3: {s3_filename}"
            )

            st.info(
                "S3 trigger activated. "
                "Document processing pipeline started."
            )

            st.session_state.s3_file_key = s3_filename

            st.session_state.processed_pdf_hash = pdf_hash

        except Exception as e:

            st.error(
                f"S3 Upload Failed: {e}"
            )

            st.stop()

    else:

        st.success(
            "Using previously uploaded document."
        )

    # =====================================================
    # QUERY SECTION
    # =====================================================

    st.divider()

    st.markdown(
        "## 🔍 Ask Your Document"
    )

    query = st.text_input(
        "Enter your query"
    )

    if query:

        # -------------------------------------------------
        # SAFETY CHECK
        # -------------------------------------------------

        if not st.session_state.s3_file_key:

            st.error(
                "Please upload a document first."
            )

            st.stop()

        # -------------------------------------------------
        # QUERY EMBEDDING
        # -------------------------------------------------

        with st.spinner(
            "Embedding query..."
        ):

            query_embedding = embed_query(
                query=query,
                client=openai_client
            )

        # -------------------------------------------------
        # RETRIEVAL
        # -------------------------------------------------

        retrieval_start = time.time()

        with st.spinner(
            "Retrieving relevant chunks..."
        ):

            retrieved_text = text_retrieval(
                client=opensearch_client,
                query_embedding=query_embedding,
                k=5,
                doc_hash=pdf_hash
            )

        retrieval_end = time.time()

        retrieval_time = (
            retrieval_end - retrieval_start
        )

        # -------------------------------------------------
        # LLM GENERATION
        # -------------------------------------------------

        llm_start = time.time()

        with st.spinner(
            "Generating answer using LLM..."
        ):

            rag_text = llm_generation(
                query=query,
                context=retrieved_text,
                llm_client=openai_client
            )

        llm_end = time.time()

        llm_response_time = (
            llm_end - llm_start
        )

        # -------------------------------------------------
        # TOTAL TIME
        # -------------------------------------------------

        total_pipeline_end = time.time()

        total_time = (
            total_pipeline_end
            - total_pipeline_start
        )

        # -------------------------------------------------
        # STORE METADATA
        # -------------------------------------------------

        try:

            store_metadata(
                pdf_name=pdf_file.name,
                query=query,
                response=rag_text,
                document_processing_time=None,
                document_embedding_time=None,
                chunk_count=None,
                embedding_count=None,
                indexing_time=None,
                retrieval_time=retrieval_time,
                retrieved_chunks_count=5,
                llm_response_time=llm_response_time,
                total_time=total_time,
                status="success"
            )

        except Exception as e:

            st.warning(
                f"Metadata logging failed: {e}"
            )

        # -------------------------------------------------
        # DISPLAY ANSWER
        # -------------------------------------------------

        st.markdown(
            "## 🧾 Answer"
        )

        st.success(rag_text)

else:

    st.info(
        "Upload a PDF to begin analysis"
    )
