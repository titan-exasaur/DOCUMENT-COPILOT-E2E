from typing import List


def index_documents_with_hash(
    client,
    chunks: List[str],
    embeddings: List[List[float]],
    doc_hash: str,
    source_key: str
):
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        doc = {
            "text": chunk,
            "embedding": embedding,
            "doc_hash": doc_hash,
            "source_key": source_key,
            "chunk_index": i
        }
        client.index(
            index="document-copilot-index",
            body=doc
        )
    print(f"Indexed {len(chunks)} chunks | doc_hash={doc_hash}")
