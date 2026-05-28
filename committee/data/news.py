"""News search via DuckDuckGo (free, no API key) for the news/sentiment analyst."""
from typing import Any, Dict, List


def search_news(query: str, max_results: int = 4, client: Any = None) -> List[Dict[str, str]]:
    """Return recent news hits as [{"title", "snippet"}] for a query.

    `client` is injectable for testing; in production it defaults to ddgs.DDGS().
    """
    if client is None:
        from ddgs import DDGS
        client = DDGS()
    hits = list(client.text(query, max_results=max_results))
    return [{"title": h.get("title", ""), "snippet": h.get("body", "")}
            for h in hits[:max_results]]
