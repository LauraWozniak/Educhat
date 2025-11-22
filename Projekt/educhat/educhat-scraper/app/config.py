import os


# Qdrant-Konfiguration
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "weiterbildungen")

# OpenAI Embedding Model
EMBED_MODEL = "text-embedding-3-small"

# Suchbegriffe für den Scraper
SEARCH_TERMS = [
    "IT Weiterbildung",
    "Pflege Ausbildung",
    "Umschulung",
    "Kaufmännische Weiterbildung",
    "Handwerk Weiterbildung"
]

# Sonstige Einstellungen
RATE_LIMIT_DELAY = 2           # Sekunden zwischen Anfragen
REQUEST_TIMEOUT = 60000        # Timeout in ms für Playwright
