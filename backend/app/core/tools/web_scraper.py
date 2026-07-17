from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.logging import logger
from app.core.tools.base import BaseTool, ToolResult


class WebScraperTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_scraper"

    @property
    def description(self) -> str:
        return (
            "Scrape and extract text content from a URL. "
            + "Use this to read articles, documentation, or any web page"
        )

    async def execute(self, *args: Any, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url", args[0] if args else "")
        max_chars = int(kwargs.get("max_chars", args[1] if len(args) > 1 else 5000))

        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                logger.info("Scraping URL: %s", url)
                response = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; AtlasResearchBot/1.0)"},
                )
                response.raise_for_status()
                logger.info(
                    "Successfully fetched %s, status: %s",
                    url,
                    response.status_code,
                )

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            text = "\n".join(line for line in text.splitlines() if line.strip())

            if len(text) > max_chars:
                text = text[:max_chars] + "\n\n[Content truncated...]"

            return ToolResult(
                success=True,
                data={
                    "url": url,
                    "content": text,
                    "word_count": len(text.split()),
                },
            )
        except httpx.TimeoutException:
            logger.error("Timeout while scraping %s", url)
            return ToolResult(success=False, error=f"Timeout scraping {url}")
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error %s while scraping %s", e.response.status_code, url)
            return ToolResult(success=False, error=f"HTTP {e.response.status_code} for {url}")
        except Exception as e:
            logger.error("Error scraping %s: %s", url, str(e))
            return ToolResult(success=False, error=str(e))

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to scrape",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to extract",
                    "default": 5000,
                },
            },
            "required": ["url"],
        }
