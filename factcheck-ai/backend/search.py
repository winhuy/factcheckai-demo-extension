import random
from typing import List, Dict, Any
from urllib.parse import urlparse
from duckduckgo_search import DDGS
from .config import whitelist_domains

class LiveSearch:
    def __init__(self):
        pass

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a live web search using DuckDuckGo.
        Returns factual snippets from various online sources.
        """
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = ddgs.text(
                    query,
                    region="wt-wt", # Wide region search for dynamic sources
                    safesearch="moderate",
                    timelimit="y", # Search past year for up to date info
                    max_results=limit * 2 # Fetch more to filter
                )
                
                for r in ddgs_results:
                    url = r.get("href")
                    if not url:
                        continue
                        
                    # Extract domain name
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.replace("www.", "")
                    
                    results.append({
                        "domain": domain,
                        "url": url,
                        "title": r.get("title", "No Title"),
                        "snippet": r.get("body", ""),
                        "is_whitelist": domain in whitelist_domains
                    })
                    
                    if len(results) >= limit:
                        break
                        
        except Exception as e:
            print(f"Live Search failed: {e}. Returning empty fallback.")
            # Return empty list to trigger internal safety mechanism in caller
            pass

        return results

# Singleton search tool instance replacement
whitelist_search = LiveSearch()
