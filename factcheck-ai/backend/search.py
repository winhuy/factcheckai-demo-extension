import asyncio
import httpx
from typing import List, Dict, Any
from urllib.parse import urlparse
from ddgs import DDGS
from bs4 import BeautifulSoup
from .config import trusted_domains


class LiveSearch:
    """
    Enhanced search module with multi-query, deep search, and page scraping capabilities.
    Provides full internet access for the Autonomous Research Agent.
    """

    def __init__(self):
        self._http_client = None

    def _get_http_client(self):
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0, connect=10.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            )
        return self._http_client

    def _is_trusted_domain(self, domain: str) -> bool:
        """
        Check if a domain belongs to the trusted sources list.
        Supports partial matching for subdomains (e.g., en.wikipedia.org matches wikipedia.org)
        """
        for trusted in trusted_domains:
            if domain == trusted or domain.endswith('.' + trusted):
                return True
        return False

    def search(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """
        Performs a live web search across the ENTIRE internet using DuckDuckGo.
        Returns factual snippets from ALL sources (not limited to whitelist).
        Sources are tagged as trusted/untrusted for UI categorization.
        """
        results = []
        try:
            with DDGS() as ddgs:
                ddgs_results = ddgs.text(
                    query,
                    region="wt-wt",  # Wide region search - entire internet
                    safesearch="moderate",
                    timelimit=None,  # No time limit - search all available content
                    max_results=limit * 2  # Fetch more for better coverage
                )

                for r in ddgs_results:
                    url = r.get("href")
                    if not url:
                        continue

                    # Extract domain name
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc.replace("www.", "")

                    # Tag source as trusted or unverified for display categorization
                    is_trusted = self._is_trusted_domain(domain)

                    results.append({
                        "domain": domain,
                        "url": url,
                        "title": r.get("title", "No Title"),
                        "snippet": r.get("body", ""),
                        "is_whitelist": is_trusted,  # backward compatible key
                        "is_trusted": is_trusted
                    })

                    if len(results) >= limit:
                        break

        except Exception as e:
            print(f"Live Search failed: {e}. Returning empty fallback.")
            pass

        return results

    def multi_search(self, queries: List[str], limit_per_query: int = 5) -> List[Dict[str, Any]]:
        """
        Executes multiple search queries and combines unique results.
        Used by the Autonomous Agent to search with different query formulations.
        Deduplicates results by URL.
        """
        all_results = []
        seen_urls = set()

        for query in queries:
            try:
                query_results = self.search(query, limit=limit_per_query)
                for result in query_results:
                    if result["url"] not in seen_urls:
                        seen_urls.add(result["url"])
                        all_results.append(result)
            except Exception as e:
                print(f"Multi-search query '{query}' failed: {e}")
                continue

        return all_results

    def deep_search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Performs a deeper search by querying with different regions and time filters.
        Used when the agent needs more comprehensive coverage.
        """
        all_results = []
        seen_urls = set()

        search_configs = [
            {"region": "wt-wt", "timelimit": None},      # Global, all time
            {"region": "vn-vi", "timelimit": None},       # Vietnam specific
            {"region": "wt-wt", "timelimit": "m"},        # Global, past month
        ]

        for config in search_configs:
            try:
                with DDGS() as ddgs:
                    ddgs_results = ddgs.text(
                        query,
                        region=config["region"],
                        safesearch="moderate",
                        timelimit=config["timelimit"],
                        max_results=limit
                    )

                    for r in ddgs_results:
                        url = r.get("href")
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        parsed_url = urlparse(url)
                        domain = parsed_url.netloc.replace("www.", "")
                        is_trusted = self._is_trusted_domain(domain)

                        all_results.append({
                            "domain": domain,
                            "url": url,
                            "title": r.get("title", "No Title"),
                            "snippet": r.get("body", ""),
                            "is_whitelist": is_trusted,
                            "is_trusted": is_trusted
                        })

                        if len(all_results) >= limit:
                            break

            except Exception as e:
                print(f"Deep search config {config} failed: {e}")
                continue

            if len(all_results) >= limit:
                break

        return all_results

    async def fetch_page_content(self, url: str, max_chars: int = 3000) -> str:
        """
        Fetches and extracts clean text content from a web page URL.
        Used by the agent to read detailed information from specific sources.
        Returns cleaned text, truncated to max_chars.
        """
        try:
            client = self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script, style, nav, footer, header elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
                tag.decompose()

            # Extract main content - try common content selectors first
            main_content = None
            for selector in ["article", "main", ".content", ".post-content", "#content", ".article-body"]:
                main_content = soup.select_one(selector)
                if main_content:
                    break

            if main_content:
                text = main_content.get_text(separator="\n", strip=True)
            else:
                # Fallback: get body text
                body = soup.find("body")
                text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)

            # Clean up: remove excessive whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = "\n".join(lines)

            return clean_text[:max_chars]

        except Exception as e:
            print(f"Failed to fetch page content from {url}: {e}")
            return ""

    async def fetch_multiple_pages(self, urls: List[str], max_chars_per_page: int = 2000) -> Dict[str, str]:
        """
        Fetches content from multiple URLs concurrently.
        Returns a dict mapping URL -> extracted text content.
        """
        tasks = [self.fetch_page_content(url, max_chars_per_page) for url in urls[:5]]  # Max 5 pages
        results = await asyncio.gather(*tasks, return_exceptions=True)

        page_contents = {}
        for url, result in zip(urls[:5], results):
            if isinstance(result, str) and result:
                page_contents[url] = result
            else:
                page_contents[url] = ""

        return page_contents


# Singleton search tool instance
whitelist_search = LiveSearch()
