# from opensearchpy import OpenSearch
# from config import HOST, PORT, USE_SSL, VERIFY_CERTS, HTTP_AUTH

# def opensearch_client_maker():
#     return OpenSearch(
#         hosts=[{"host": HOST, "port": PORT}],
#         use_ssl=USE_SSL,
#         verify_certs=VERIFY_CERTS,
#         http_auth=HTTP_AUTH
#     )


import os
from dotenv import load_dotenv
from opensearchpy import OpenSearch

load_dotenv()

OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD")


def opensearch_client_maker():

    client = OpenSearch(
        hosts=[{
            "host": OPENSEARCH_HOST.replace("https://", ""),
            "port": 443
        }],

        http_auth=(
            OPENSEARCH_USERNAME,
            OPENSEARCH_PASSWORD
        ),

        use_ssl=True,
        verify_certs=True
    )

    return client