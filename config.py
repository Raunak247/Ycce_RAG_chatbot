import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ycce.edu/"
DOMAIN = "ycce.edu"
MAX_DEPTH = 4
RATE_LIMIT = 1

SIMILARITY_THRESHOLD = 0.35

DATA_DIR = "data"
FAISS_PATH = os.path.join(DATA_DIR, "faiss_index")
DISCOVERED_URLS = os.path.join(DATA_DIR, "discovered_urls.json")
REGISTRY_PATH = os.path.join(DATA_DIR, "url_registry.json")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")