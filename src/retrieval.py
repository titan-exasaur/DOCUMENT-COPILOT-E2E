from config import INDEX_NAME


def text_retrieval(
    client,
    query_embedding,
    k=5,
    doc_hash=None
):
    """
    Performs semantic vector retrieval using
    OpenSearch k-NN search.

    Supports document-level filtering using
    document hash isolation to avoid
    cross-document contamination.

    Parameters
    ----------
    client : OpenSearch
        OpenSearch client instance.

    query_embedding : list or numpy.ndarray
        Query embedding vector.

    k : int, optional
        Number of top chunks to retrieve.
        Default is 5.

    doc_hash : str, optional
        Unique document hash used for
        filtering retrieval results.

    Returns
    -------
    str
        Combined retrieved context text.
    """

    # =========================================
    # CONVERT NUMPY -> LIST
    # =========================================

    if hasattr(query_embedding, "tolist"):
        query_embedding = query_embedding.tolist()

    # =========================================
    # BUILD SEARCH QUERY
    # =========================================

    search_query = {
        "size": k,

        "query": {
            "bool": {

                "must": [

                    {
                        "knn": {
                            "embedding": {
                                "vector": query_embedding,
                                "k": k
                            }
                        }
                    }

                ],

                "filter": []
            }
        }
    }

    # =========================================
    # DOCUMENT ISOLATION FILTER
    # =========================================

    if doc_hash is not None:

        search_query["query"]["bool"]["filter"].append(
            {
                "term": {
                    "doc_hash": doc_hash
                }
            }
        )

    # =========================================
    # SEARCH OPENSEARCH
    # =========================================

    response = client.search(
        index=INDEX_NAME,
        body=search_query
    )

    # =========================================
    # EXTRACT RETRIEVED CHUNKS
    # =========================================

    results = []

    for hit in response["hits"]["hits"]:

        results.append({

            "text": hit["_source"]["text"],

            "score": hit["_score"]
        })

    # =========================================
    # BUILD FINAL CONTEXT
    # =========================================

    retrieved_chunks = [
        result["text"]
        for result in results
    ]

    context = "\n\n".join(retrieved_chunks)

    return context