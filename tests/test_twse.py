from datetime import date

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


def test_institutional_flows_parses_t86_net_columns(tmp_path):
    # 19 columns; indices 4=foreign, 10=trust, 11=dealer, 18=total (net shares).
    row = ["2330", "台積電", "x", "x", "12,000", "x", "x", "x", "x", "x",
           "3,000", "-1,500", "x", "x", "x", "x", "x", "x", "13,500"]
    payload = {"stat": "OK", "date": "20260504", "data": [row]}
    session = _FakeSession({"T86": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session, today=date(2026, 5, 4))

    out = client.institutional_flows("2330")
    assert out == {"stock_no": "2330", "name": "台積電", "foreign_net": 12000,
                   "trust_net": 3000, "dealer_net": -1500, "total_net": 13500,
                   "date": "20260504"}


def test_monthly_revenue_found(tmp_path):
    payload = [{"公司代號": "2330", "公司名稱": "台積電", "資料年月": "11504",
                "營業收入-當月營收": "257219",
                "營業收入-去年同月增減(%)": "39.0",
                "營業收入-上月比較增減(%)": "5.0"}]
    session = _FakeSession({"t187ap05_P": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session, today=date(2026, 5, 27))

    out = client.monthly_revenue("2330")
    assert out["available"] is True
    assert out["revenue"] == "257219" and out["yoy_pct"] == "39.0"


def test_monthly_revenue_missing_is_graceful(tmp_path):
    session = _FakeSession({"t187ap05_P": [{"公司代號": "9999"}]})
    client = TwseClient(cache_dir=str(tmp_path), session=session, today=date(2026, 5, 27))

    out = client.monthly_revenue("2330")
    assert out["available"] is False and "暫無" in out["note"]


def test_index_history_parses_taiex_close(tmp_path):
    payload = {"stat": "OK",
               "fields": ["日期", "開盤指數", "最高指數", "最低指數", "收盤指數"],
               "data": [["115/05/02", "100.00", "110.00", "95.00", "105.00"],
                        ["115/05/03", "105.00", "115.00", "100.00", "112.00"]]}
    session = _FakeSession({"MI_5MINS_HIST": payload})
    client = TwseClient(cache_dir=str(tmp_path), session=session)

    rows = client.index_history(months=1)
    assert rows[0] == {"date": "2026-05-02", "close": 105.0}
    assert rows[-1] == {"date": "2026-05-03", "close": 112.0}


_INCOME_ROW = {"公司代號": "2330", "公司名稱": "台積電", "年度": "115", "季別": "1",
               "營業收入": "800000.00", "營業毛利（毛損）淨額": "480000.00",
               "營業利益（損失）": "400000.00", "本期淨利（淨損）": "360000.00",
               "基本每股盈餘（元）": "13.94"}
_BALANCE_ROW = {"公司代號": "2330", "權益總額": "3600000.00", "每股參考淨值": "150.50"}


def test_financials_found_computes_margins_and_roe(tmp_path):
    session = _FakeSession({"t187ap06_L_ci": [_INCOME_ROW],
                            "t187ap07_L_ci": [_BALANCE_ROW]})
    client = TwseClient(cache_dir=str(tmp_path), session=session, today=date(2026, 5, 27))

    out = client.financials("2330")
    assert out["available"] is True
    assert out["period"] == "115Q1"
    assert out["gross_margin_pct"] == 60.0       # 480000 / 800000
    assert out["operating_margin_pct"] == 50.0   # 400000 / 800000
    assert out["roe_pct"] == 10.0                # 360000 / 3600000
    assert out["eps"] == 13.94
    assert out["book_value_per_share"] == 150.5


def test_financials_missing_is_graceful(tmp_path):
    session = _FakeSession({"t187ap06_L_ci": [{"公司代號": "9999"}],
                            "t187ap07_L_ci": []})
    client = TwseClient(cache_dir=str(tmp_path), session=session, today=date(2026, 5, 27))

    out = client.financials("2330")
    assert out["available"] is False and "暫無" in out["note"]
