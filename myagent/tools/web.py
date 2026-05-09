"""Web tools."""

from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from myagent.tools.base import Tool


class WebSearchTool(Tool):
    """Search the web and return compact text results."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        search_url: str = "https://duckduckgo.com/html/",
    ) -> None:
        self.client = client
        self.search_url = search_url

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the public web for current or external information. "
            "Use when local files and memory are not enough."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return.",
                    "minimum": 1,
                    "maximum": 10,
                },
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        max_results: int = 5,
        **_: Any,
    ) -> str:
        text = query.strip()
        if not text:
            return "Error: query must not be empty."
        limit = min(max(max_results, 1), 10)
        try:
            html = await self._fetch(text)
        except Exception as exc:
            return f"Error: web search failed: {exc}"

        results = _parse_search_results(html, limit)
        if not results:
            return f"No web search results found for: {text}"
        return "\n\n".join(
            f"{index}. {result.title}\n{result.url}\n{result.snippet}".strip()
            for index, result in enumerate(results, 1)
        )

    async def _fetch(self, query: str) -> str:
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        try:
            response = await client.get(
                f"{self.search_url}?{urlencode({'q': query})}",
                headers={"User-Agent": "MyAgent/0.1 web_search"},
            )
            response.raise_for_status()
            return response.text
        finally:
            if owns_client:
                await client.aclose()


class WebFetchTool(Tool):
    """Fetch one web page and return readable text."""

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self.client = client

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return (
            "Fetch a URL from the public web and return readable text. "
            "Use after web_search when search snippets are not enough."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTP or HTTPS URL to fetch.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum number of text characters to return.",
                    "minimum": 200,
                    "maximum": 20000,
                },
            },
            "required": ["url"],
        }

    async def execute(
        self,
        url: str,
        max_chars: int = 6000,
        **_: Any,
    ) -> str:
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"}:
            return "Error: url must start with http:// or https://."
        limit = min(max(max_chars, 200), 20000)
        owns_client = self.client is None
        client = self.client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        try:
            response = await client.get(
                url,
                headers={"User-Agent": "MyAgent/0.1 web_fetch"},
            )
            response.raise_for_status()
            text = _html_to_text(response.text)
        except Exception as exc:
            return f"Error: web fetch failed: {exc}"
        finally:
            if owns_client:
                await client.aclose()
        if not text:
            return f"No readable text found at: {url}"
        if len(text) > limit:
            return text[:limit].rstrip() + f"\n\n(truncated to {limit} characters)"
        return text


class SearchResult:
    """One parsed search result."""

    def __init__(self, title: str, url: str, snippet: str) -> None:
        self.title = title
        self.url = url
        self.snippet = snippet


class _DuckDuckGoHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchResult] = []
        self._in_title = False
        self._in_snippet = False
        self._current_title: list[str] = []
        self._current_url = ""
        self._current_snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._finish_result()
            self._in_title = True
            self._current_title = []
            self._current_url = _clean_result_url(attr.get("href") or "")
            self._current_snippet = []
        elif "result__snippet" in classes:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
        elif self._in_snippet:
            self._in_snippet = False
            self._finish_result()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._current_title.append(data)
        elif self._in_snippet:
            self._current_snippet.append(data)

    def close(self) -> None:
        super().close()
        self._finish_result()

    def _finish_result(self) -> None:
        title = _compact_text(" ".join(self._current_title))
        if not title or not self._current_url:
            return
        snippet = _compact_text(" ".join(self._current_snippet))
        if not any(result.url == self._current_url for result in self.results):
            self.results.append(SearchResult(title=title, url=self._current_url, snippet=snippet))
        self._current_title = []
        self._current_url = ""
        self._current_snippet = []


def _parse_search_results(html: str, limit: int) -> list[SearchResult]:
    parser = _DuckDuckGoHtmlParser()
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _clean_result_url(url: str) -> str:
    parsed = urlparse(unescape(url))
    query = parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return query["uddg"][0]
    return unescape(url)


def _compact_text(text: str) -> str:
    return " ".join(unescape(text).split())


class _ReadableTextParser(HTMLParser):
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        elif tag in {"p", "br", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in {"p", "div", "section", "article", "li", "tr", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)


def _html_to_text(html: str) -> str:
    parser = _ReadableTextParser()
    parser.feed(html)
    parser.close()
    lines = [_compact_text(line) for line in " ".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)
