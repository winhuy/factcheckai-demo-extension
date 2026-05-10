import os

# API Configurations
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Whitelist domains for Vietnamese news & official government portals
DEFAULT_WHITELIST_DOMAINS = [
    "vnexpress.net",
    "tuoitre.vn",
    "thanhnien.vn",
    "nhandan.vn",
    "chinhphu.vn",
    "vtv.vn",
    "baochinhphu.vn",
    "vietnamnet.vn",
    "laodong.vn",
    "qdnd.vn",
    "vov.vn"
]

# We support adding/removing domains dynamically at runtime, so we can keep a dynamic list
whitelist_domains = list(DEFAULT_WHITELIST_DOMAINS)

# Cache Configurations
CACHE_FILE = "factcheck_cache.json"

# App settings
DEBUG = True
HOST = "127.0.0.1"
PORT = 8000
