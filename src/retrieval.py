from config import INDEX_NAME

def text_retrieval(client, query_embedding, k=5):
    """
    Performs semantic search using OpenSearch k-NN.
    """

    if hasattr(query_embedding, "tolist"):
        query_embedding = query_embedding.tolist()

    response = client.search(
        index=INDEX_NAME,
        body={
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": k
                    }
                }
            }
        }
    )

    results = []

    for hit in response["hits"]["hits"]:
        results.append({
            "text": hit["_source"]["text"],
            "score": hit["_score"]
        })

    retrieved_chunks = []

    context = "\n\n".join(retrieved_chunks)

    return context