from opensearchpy import OpenSearch
from config import HOST, PORT, USE_SSL, VERIFY_CERTS, HTTP_AUTH

def opensearch_client_maker():
    return OpenSearch(
        hosts=[{"host": HOST, "port": PORT}],
        use_ssl=USE_SSL,
        verify_certs=VERIFY_CERTS,
        http_auth=HTTP_AUTH
    )