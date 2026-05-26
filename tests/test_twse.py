from committee.data.twse import TwseClient, roc_to_iso, to_float


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, by_url):
        self._by_url = by_url
        self.requested = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.requested.append((url, params))
        for key, payload in self._by_url.items():
            if key in url:
                return _FakeResp(payload)
        raise AssertionError("unexpected url: " + url)


def test_roc_to_iso_and_to_float_helpers():
    assert roc_to_iso("115/05/02") == "2026-05-02"
    assert to_float("1,234.50") == 1234.5
    assert to_float("--") is None


def test_valuation_parses_bwibbu_all_row(tmp_path):
    payload = {"fields": ["股票代號", "股票名稱", "本益比", "殖利率(%)", "股價淨值比"],
               "data": [["2330", "台積電", "22.50", "1.85", "6.30"],
                        ["2317", "鴻海", "10.10", "4.10", "1.20"]]}
    session = _FakeSession({"BWIBBU_ALL": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)

    val = client.valuation("2330")
    assert val == {"stock_no": "2330", "name": "台積電",
                   "pe": 22.5, "pb": 6.3, "dividend_yield": 1.85}


def test_price_history_parses_and_orders_rows(tmp_path):
    payload = {"stat": "OK",
               "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價",
                          "最低價", "收盤價", "漲跌價差", "成交筆數", "註記"],
               "data": [["115/05/02", "20,000,000", "1", "900.00", "910.00",
                         "895.00", "905.00", "+5.00", "30000", ""],
                        ["115/05/03", "21,000,000", "1", "906.00", "915.00",
                         "900.00", "912.00", "+7.00", "31000", ""]]}
    session = _FakeSession({"STOCK_DAY": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)

    rows = client.price_history("2330", months=1)
    assert rows[0] == {"date": "2026-05-02", "open": 900.0, "high": 910.0,
                       "low": 895.0, "close": 905.0, "volume": 20000000}
    assert rows[-1]["date"] == "2026-05-03"


def test_disk_cache_avoids_second_network_call(tmp_path):
    payload = {"fields": ["股票代號", "股票名稱", "本益比", "殖利率(%)", "股價淨値比"],
               "data": [["2330", "台積電", "22.50", "1.85", "6.30"]]}
    session = _FakeSession({"BWIBBU_ALL": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)
    client.valuation("2330")
    client.valuation("2330")
    # BWIBBU_ALL is one snapshot for the day -> only one network call.
    assert len(session.requested) == 1
