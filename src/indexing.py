from opensearchpy import helpers

from config import INDEX_NAME, EMBEDDING_DIM


def create_index_if_not_exists(client):
    """
    Creates the OpenSearch vector index if it does not already exist.

    Index contains:
    - text field for chunk content
    - knn_vector field for semantic embeddings
    - doc_hash keyword field for document isolation

    Parameters
    ----------
    client : OpenSearch
        OpenSearch client instance.
    """

    index_body = {
        "settings": {
            "index": {
                "knn": True
            }
        },

        "mappings": {
            "properties": {

                "text": {
                    "type": "text"
                },

                "embedding": {
                    "type": "knn_vector",
                    "dimension": EMBEDDING_DIM
                },

                "doc_hash": {
                    "type": "keyword"
                }
            }
        }
    }

    if not client.indices.exists(index=INDEX_NAME):

        client.indices.create(
            index=INDEX_NAME,
            body=index_body
        )

        print(f"[INFO] Index '{INDEX_NAME}' created")

    else:

        print(f"[INFO] Index '{INDEX_NAME}' already exists")


def document_indexing(chunks, embeddings, client):
    """
    Bulk indexes chunk embeddings into OpenSearch.

    Each indexed document contains:
    - chunk text
    - embedding vector
    - document hash for retrieval isolation

    Parameters
    ----------
    chunks : list
        List of chunk dictionaries.
        Example:
        {
            "text": "...",
            "doc_hash": "abc123"
        }

    embeddings : list
        List of embedding vectors.

    client : OpenSearch
        OpenSearch client instance.
    """

    # =========================================
    # SAFETY CHECK
    # =========================================

    if len(chunks) != len(embeddings):

        raise ValueError(
            "Chunks and embeddings length mismatch"
        )

    # =========================================
    # BULK ACTIONS
    # =========================================

    actions = []

    for i, (doc, embedding) in enumerate(
        zip(chunks, embeddings)
    ):

        # -------------------------------------
        # EXTRACT TEXT
        # -------------------------------------

        text_value = doc["text"]

        # -------------------------------------
        # FORCE STRING SAFETY
        # -------------------------------------

        if not isinstance(text_value, str):

            text_value = str(text_value)

        # -------------------------------------
        # BUILD DOCUMENT
        # -------------------------------------

        actions.append({

            "_index": INDEX_NAME,

            "_id": f"{doc.get('doc_hash', 'unknown')}_{i}",

            "_source": {

                "text": text_value,

                "embedding": embedding.tolist(),

                "doc_hash": doc.get(
                    "doc_hash",
                    None
                )
            }
        })

    # =========================================
    # BULK INDEXING
    # =========================================

    helpers.bulk(
        client,
        actions
    )

    print(
        f"[INFO] Indexed {len(actions)} documents successfully"
    )