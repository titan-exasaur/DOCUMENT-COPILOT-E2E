import os, sys
import streamlit as st
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

from src.ingestion import document_loader
from src.chunking import chunk_text
from src.embeddings import embedding_text
from src.opensearch_client import opensearch_client_maker
from src.indexing import create_index_if_not_exists, document_indexing
from src.retrieval import text_retrieval
from src.generation import llm_generation

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

sys.path.append('src/')

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
        .card {
            padding: 1.2rem;
            border-radius: 12px;
            background: #1a1c23;
            border: 1px solid #2a2d36;
        }
        .title {
            font-size: 40px;
            font-weight: 700;
            background: linear-gradient(90deg, #00C6FF, #0072FF);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown("<div class='title'>📄 Document Co-Pilot</div>", unsafe_allow_html=True)
st.caption("AI-powered PDF understanding using RAG + OpenSearch + LLMs")

@st.cache_resource
def get_client():
    return opensearch_client_maker()

opensearch_client = get_client()

pdf_file = st.file_uploader("Upload PDF file", type=["pdf"])

if pdf_file is not None:

    pdf_text = document_loader(pdf_file)
    st.success("PDF loaded successfully")

    texts = [doc["text"] for doc in pdf_text]
    chunks = chunk_text(texts)
    st.info(f"Total Chunks: {len(chunks)}")


    model, embeddings = embedding_text(chunks)
    st.info(f"Total Embeddings: {len(embeddings)}")

    with st.spinner("Indexing into OpenSearch..."):
        create_index_if_not_exists(opensearch_client)
        document_indexing(
            chunks=chunks,
            embeddings=embeddings,
            client=opensearch_client
        )
        st.info("Indexing complete")

    st.divider()

    st.markdown("### 🔍 Ask Your Document")

    query = st.text_input("Enter your query")

    if query:

        with st.spinner("Generating embedding..."):
            query_embedding = model.encode(query)

        with st.spinner("Retrieving relevant context..."):
            retrieved_text = text_retrieval(
                opensearch_client,
                query_embedding,
                k=5
            )


        with st.spinner("Generating answer..."):
            rag_text = llm_generation(
                query=query,
                context=retrieved_text,
                llm_client=openai_client
            )

        st.markdown("### 🧾 Answer")
        st.success(rag_text)

    else:
        st.warning("Write a query")

else:
    st.info("Upload a PDF to begin analysis")