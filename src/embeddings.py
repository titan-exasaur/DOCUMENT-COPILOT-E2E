import os
from typing import List


def embedding_text(chunks: List[str], debug: bool = False):
    """
    Original function — local SentenceTransformer embeddings.
    Used by local pipeline on EC2.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(chunks, show_progress_bar=debug)
    return embeddings.tolist()


def embed_chunks_api(chunks: List[str], client) -> List[List[float]]:
    """
    Lambda function — embeds chunks via OpenAI API.
    No local model needed.
    """
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunks
    )
    return [item.embedding for item in response.data]
