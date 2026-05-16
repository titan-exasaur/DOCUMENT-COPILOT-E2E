from opensearchpy import helpers
from config import INDEX_NAME, EMBEDDING_DIM


def create_index_if_not_exists(client):
    index_body = {
        "settings": {
            "index": {
                "knn": True
            }
        },
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM
                },
                "doc_hash": {"type": "keyword"}
            }
        }
    }

    if not client.indices.exists(index=INDEX_NAME):
        client.indices.create(index=INDEX_NAME, body=index_body)
        print(f"[INFO] Index '{INDEX_NAME}' created")
    else:
        print(f"[INFO] Index '{INDEX_NAME}' already exists")


def document_indexing(chunks, embeddings, client):
    """
    Bulk indexes documents into OpenSearch.
    """

    if len(chunks) != len(embeddings):
        raise ValueError("Chunks and embeddings length mismatch")

    actions = []

    for i, (doc, embedding) in enumerate(zip(chunks, embeddings)):

        text_value = doc["text"]

        # FORCE STRING SAFETY (CRITICAL FIX)
        if not isinstance(text_value, str):
            text_value = str(text_value)

        actions.append({
            "_index": INDEX_NAME,
            "_id": i,
            "_source": {
                "text": text_value,
                "embedding": embedding.tolist(),
                "doc_hash": doc.get("doc_hash", None)
            }
        })

    helpers.bulk(client, actions)

    print(f"[INFO] Indexed {len(actions)} documents successfully")