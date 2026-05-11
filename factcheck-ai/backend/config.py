import os

# API Configurations
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Trusted domains for Vietnamese news & official government portals
# These are used for CATEGORIZATION only (green = verified source, yellow = unverified)
# Search now covers the entire internet - these domains help visually tag source reliability
DEFAULT_TRUSTED_DOMAINS = [
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
    "vov.vn",
    # International trusted sources
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "nytimes.com",
    "who.int",
    "un.org",
    "wikipedia.org",
    "gov.vn"
]

# We support adding/removing domains dynamically at runtime, so we can keep a dynamic list
# Also keep backward-compatible alias
trusted_domains = list(DEFAULT_TRUSTED_DOMAINS)
whitelist_domains = trusted_domains  # backward-compatible alias

# Cache Configurations
CACHE_FILE = "factcheck_cache.json"

# App settings
DEBUG = True
HOST = "127.0.0.1"
PORT = 8000
