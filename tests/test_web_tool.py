import httpx

from myagent.tools.web import WebFetchTool, WebSearchTool


def make_client(html: str, status_code: int = 200) -> httpx.AsyncClient:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code,
            headers={"content-type": "text/html"},
            text=html,
            request=request,
        )
    )
    return httpx.AsyncClient(transport=transport)


async def test_web_search_tool_returns_compact_results() -> None:
    html = """
    <html>
      <a class="result__a" href="/l/?uddg=https%3A%2F%2Fexample.com%2Fone">First Result</a>
      <a class="result__snippet">A useful snippet.</a>
      <a class="result__a" href="https://example.com/two">Second Result</a>
      <a class="result__snippet">Another snippet.</a>
    </html>
    """
    client = make_client(html)
    tool = WebSearchTool(client=client)

    result = await tool.execute(query="example", max_results=1)

    assert "1. First Result" in result
    assert "https://example.com/one" in result
    assert "A useful snippet." in result
    assert "Second Result" not in result
    await client.aclose()


async def test_web_search_tool_reports_no_results() -> None:
    client = make_client("<html></html>")
    tool = WebSearchTool(client=client)

    result = await tool.execute(query="nothing")

    assert result == "No web search results found for: nothing"
    await client.aclose()


async def test_web_search_tool_reports_http_errors() -> None:
    client = make_client("nope", status_code=500)
    tool = WebSearchTool(client=client)

    result = await tool.execute(query="failure")

    assert result.startswith("Error: web search failed:")
    await client.aclose()


async def test_web_fetch_tool_returns_readable_text() -> None:
    html = """
    <html>
      <head><style>.hidden {}</style><script>bad()</script></head>
      <body>
        <h1>Weather Forecast</h1>
        <p>Tomorrow will be sunny.</p>
      </body>
    </html>
    """
    client = make_client(html)
    tool = WebFetchTool(client=client)

    result = await tool.execute(url="https://example.com/weather", max_chars=200)

    assert "Weather Forecast" in result
    assert "Tomorrow will be sunny." in result
    assert "bad()" not in result
    await client.aclose()


async def test_web_fetch_tool_rejects_non_http_urls() -> None:
    tool = WebFetchTool()

    result = await tool.execute(url="file:///secret.txt")

    assert result == "Error: url must start with http:// or https://."
