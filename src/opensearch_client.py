import os
from opensearchpy import OpenSearch


def opensearch_client_maker():
    host = os.getenv("OPENSEARCH_HOST", "")
    username = os.getenv("OPENSEARCH_USERNAME", "")
    password = os.getenv("OPENSEARCH_PASSWORD", "")

    host = host.replace("https://", "").replace("http://", "")

    client = OpenSearch(
        hosts=[{
            "host": host,
            "port": 443
        }],
        http_auth=(username, password),
        use_ssl=True,
        verify_certs=True
    )
    return client
