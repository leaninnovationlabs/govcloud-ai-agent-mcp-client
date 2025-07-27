import asyncio
import logging
from typing import Optional
from urllib.parse import quote

import httpx
from pydantic import ValidationError

from .models import WikipediaSearchResponse, WikipediaArticle, WikipediaSearchResult

logger = logging.getLogger(__name__)


class WikipediaService:
    def __init__(self, timeout: float = 10.0):
        self._client: Optional[httpx.AsyncClient] = None
        self._timeout = timeout

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"User-Agent": "WikipediaMCP/2.0"},
                follow_redirects=True
            )
        return self._client

    async def search_articles(
        self, query: str, limit: int = 10, lang: str = "en"
    ) -> WikipediaSearchResponse:
        if not query.strip():
            return WikipediaSearchResponse(
                query=query, results=[], total_count=0, language=lang
            )

        try:
            client = await self._get_client()
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": min(limit, 50),
                    "srprop": "snippet|titlesnippet|size",
                }
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.warning(f"Wikipedia API error: {data['error']}")
                return WikipediaSearchResponse(
                    query=query, results=[], total_count=0, language=lang
                )

            search_results = data.get("query", {}).get("search", [])
            results = [
                WikipediaSearchResult(
                    title=item["title"],
                    description=self._clean_snippet(item.get("snippet", "")),
                    url=f"https://{lang}.wikipedia.org/wiki/{quote(item['title'].replace(' ', '_'))}",
                )
                for item in search_results
            ]

            return WikipediaSearchResponse(
                query=query,
                results=results,
                total_count=len(results),
                language=lang
            )

        except httpx.RequestError as e:
            logger.error(f"Network error during search: {e}")
            return WikipediaSearchResponse(
                query=query, results=[], total_count=0, language=lang
            )
        except Exception as e:
            logger.error(f"Unexpected error during search: {e}")
            return WikipediaSearchResponse(
                query=query, results=[], total_count=0, language=lang
            )

    async def get_article(self, title: str, lang: str = "en") -> WikipediaArticle:
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "titles": title,
                    "prop": "extracts|info",
                    "exintro": False,
                    "explaintext": True,
                    "inprop": "url",
                }
            )
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            if not pages:
                raise ValueError(f"Article '{title}' not found")

            page = next(iter(pages.values()))
            if "missing" in page:
                raise ValueError(f"Article '{title}' does not exist")

            extract = page.get("extract", "")
            summary = extract[:500] + "..." if len(extract) > 500 else extract

            return WikipediaArticle(
                title=page["title"],
                content=extract,
                summary=summary,
                url=page.get("fullurl", f"https://{lang}.wikipedia.org/wiki/{quote(title)}"),
                language=lang,
                last_modified=page.get("touched"),
            )

        except httpx.RequestError as e:
            logger.error(f"Network error fetching article '{title}': {e}")
            raise ValueError(f"Failed to fetch article due to network error") from e
        except ValidationError as e:
            logger.error(f"Data validation error for article '{title}': {e}")
            raise ValueError(f"Invalid article data received") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching article '{title}': {e}")
            raise ValueError(f"Failed to fetch article: {str(e)}") from e

    async def get_article_summary(self, title: str, lang: str = "en") -> str:
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "titles": title,
                    "prop": "extracts",
                    "exintro": True,
                    "explaintext": True,
                    "exsectionformat": "plain",
                }
            )
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return f"No summary available for '{title}'"

            page = next(iter(pages.values()))
            if "missing" in page:
                return f"Article '{title}' does not exist"

            return page.get("extract", f"No summary available for '{title}'")

        except Exception as e:
            logger.error(f"Error fetching summary for '{title}': {e}")
            return f"Failed to get summary: {str(e)}"

    async def get_random_article(self, lang: str = "en") -> WikipediaArticle:
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "list": "random",
                    "rnnamespace": "0",
                    "rnlimit": "1",
                }
            )
            response.raise_for_status()
            data = response.json()

            random_pages = data.get("query", {}).get("random", [])
            if not random_pages:
                raise ValueError("Could not retrieve random article")

            title = random_pages[0]["title"]
            return await self.get_article(title, lang)

        except Exception as e:
            logger.error(f"Error fetching random article: {e}")
            raise ValueError(f"Failed to get random article: {str(e)}") from e

    async def article_exists(self, title: str, lang: str = "en") -> bool:
        try:
            client = await self._get_client()
            response = await client.get(
                f"https://{lang}.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "format": "json",
                    "titles": title,
                }
            )
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            if not pages:
                return False

            page = next(iter(pages.values()))
            return "missing" not in page

        except Exception as e:
            logger.error(f"Error checking if article exists '{title}': {e}")
            return False

    def _clean_snippet(self, snippet: str) -> str:
        return (
            snippet.replace("<span class=\"searchmatch\">", "")
            .replace("</span>", "")
            .strip()
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()