from typing import List

def chunk_text(documents: List[str], chunk_size=500, chunk_overlap=50) -> List[str]:
    """
    Splits documents into overlapping chunks.

    Args:
        documents: List of text strings
        chunk_size: size of each chunk
        chunk_overlap: overlap between chunks

    Returns:
        List of text chunks
    """

    chunks = []

    for text in documents:
        start = 0  # reset per document

        while start < len(text):
            end = start + chunk_size

            chunks.append(text[start:end])

            start += chunk_size - chunk_overlap

    return chunks