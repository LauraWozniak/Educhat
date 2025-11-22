from qdrant_client import QdrantClient

# Für lokal ausgeführtes Python:
client = QdrantClient(url="http://localhost:6333")

# Liste der Collections
print(client.get_collections())
