from committee.data.news import search_news


class _FakeDDGS:
    def __init__(self, hits):
        self._hits = hits
        self.query = None

    def text(self, query, max_results=4):
        self.query = query
        return self._hits


def test_search_news_maps_title_and_snippet():
    fake = _FakeDDGS([
        {"title": "台積電大漲", "href": "http://x", "body": "今日上漲..."},
        {"title": "法人買超", "href": "http://y", "body": "外資..."},
    ])
    out = search_news("台積電", max_results=2, client=fake)
    assert out == [
        {"title": "台積電大漲", "snippet": "今日上漲..."},
        {"title": "法人買超", "snippet": "外資..."},
    ]
    assert fake.query == "台積電"


def test_search_news_truncates_to_max_results():
    fake = _FakeDDGS([{"title": str(i), "body": "b"} for i in range(10)])
    out = search_news("q", max_results=3, client=fake)
    assert len(out) == 3
