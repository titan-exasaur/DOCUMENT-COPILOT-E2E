from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

# Load model ONCE (global scope)
model = SentenceTransformer('all-MiniLM-L6-v2')

def embedding_text(chunks: List[str], debug: bool = False):
    """
    Converts text chunks into embedding vectors.
    
    Args:
        chunks: List of text strings
    
    Returns:
        embedding model
        numpy array of embeddings
    """

    embeddings = model.encode(chunks)

    if debug:
        print(f"Number of embeddings: {len(embeddings)}")
        print(f"Embedding dimension: {len(embeddings[0])}")
        print(f"First embedding sample: {embeddings[0][:5]}...")

    return model, embeddings