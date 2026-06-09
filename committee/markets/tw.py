# committee/markets/tw.py
"""Taiwan market profile: Chinese prompts, templates, tool descriptions, labels."""
from committee.markets.base import Prompts, ReportLabels, Templates, ToolDescriptions


def tw_prompts() -> Prompts:
    return Prompts(
        fundamental=(
            "你是一位專注台股的基本面分析師。請使用 get_valuation 取得本益比、股價淨值比與"
            "殖利率,get_monthly_revenue 取得最新月營收年增率,並用 get_financials 取得最新一季"
            "毛利率、營業利益率、ROE 與 EPS,綜合判斷估值、獲利能力與成長性。"
            "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
            "切勿捏造數字;若工具失敗或資料暫無,請直接說明。"
        ),
        technical=(
            "你是一位專注台股的技術面分析師。請使用 get_technical_indicators 取得均線、趨勢、"
            "動能與震盪指標(RSI14、KD、MACD),並用 get_relative_strength 取得相對大盤的超額"
            "報酬與 beta,綜合判斷趨勢、超買超賣、相對強弱與進場時機。"
            "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
            "切勿捏造數字;若工具失敗或某指標為 null(資料不足),請直接說明,不要臆測。"
        ),
        institutional=(
            "你是一位專注台股的籌碼面分析師。請使用 get_institutional_flows 取得三大法人"
            "(外資/投信/自營商)買賣超,判斷主力資金是進場或出場。請以繁體中文、精簡作答"
            "(120字以內),最後以明確傾向作結:看多、看空 或 中性。切勿捏造數字。"
        ),
        news=(
            "你是一位專注台股的新聞輿情分析師。請使用 search_news 搜尋該公司的近期新聞,"
            "歸納利多/利空與市場情緒。請以繁體中文、精簡作答(120字以內),最後以明確傾向"
            "作結:看多、看空 或 中性。僅引用新聞重點,不要捏造未出現的內容。"
        ),
        risk=(
            "你是投資委員會的風險經理。請使用 get_risk_metrics 取得年化波動率與最大回撤,"
            "評估下檔風險,並對其他分析師過於樂觀之處提出質疑。請以繁體中文、精簡作答"
            "(120字以內)。切勿捏造數字。"
        ),
        skeptic=(
            "你是委員會的唱反調者(魔鬼代言人),沒有任何工具。你的任務是挑戰目前浮現的"
            "共識、找出論點的弱點與盲點,避免團體迷思。請以繁體中文、犀利但具體地提出"
            "2-3 個反對理由(120字以內)。"
        ),
        chair=(
            "你是投資委員會的主席。你會收到各委員的意見與彼此的質詢答辯,必須做出單一的"
            "最終結論。請完全以繁體中文,並嚴格依下列格式輸出:第一行「建議: 買進｜持有｜賣出」"
            "(三擇一),第二行「信心: NN%」,接著一段引用各委員論點的理由。除委員提供的"
            "數字外,不得自行捏造數字。"
        ),
        verifier=(
            "你是委員會的查核員。你會看到主席的結論與委員引用的數據。請以繁體中文檢查結論"
            "是否與實際數據一致、推理是否合理,並指出任何沒有數據支持或前後矛盾之處。"
            "若全部一致,請回覆『查核通過』;否則簡要列出問題。"
        ),
    )


def tw_templates() -> Templates:
    return Templates(
        analyst=(
            "請從你的專業角度分析台股 {stock}。請先使用你的工具取得真實資料,"
            "再給出精簡看法,並以 看多/看空/中性 的傾向作結。"
        ),
        challenge=(
            "以下是各分析師對台股 {stock} 的意見。請從你的角度提出質疑與風險,"
            "挑戰其中過於樂觀或證據不足的論點。"
        ),
        rebuttal=(
            "風險經理與唱反調者提出了上述質疑。請針對與你專業相關的部分,"
            "用一段話回應或修正你先前對台股 {stock} 的看法。"
        ),
        reflect=(
            "以下是你對台股 {stock} 的初步結論。請重新檢視自己的推理:論點是否紮實、前後是否一致、"
            "每個數字是否有委員引用的數據支持。若發現問題請修正,然後**只輸出**改良後的最終建議,"
            "並嚴格維持原本格式(第一行「建議: 買進｜持有｜賣出」、第二行「信心: NN%」、接著理由);"
            "不得加入格式以外的說明,也不得捏造新數字。"
        ),
        verify=(
            "請檢視委員會對台股 {stock} 的結論是否與各委員引用的數據一致,"
            "指出任何沒有數據支持的數字或前後矛盾之處;若無問題請回覆「查核通過」。"
        ),
        correction=(
            "查核發現以下數字未獲數據支持:{figures}。請重新修正對台股 {stock} 的建議,"
            "只使用有數據支持的數字,並維持原本的輸出格式。"
        ),
    )


def tw_tool_descriptions() -> ToolDescriptions:
    return ToolDescriptions(
        stock_param="Taiwan stock code, e.g. 2330",
        get_valuation="Get P/E, P/B and dividend yield for a Taiwan stock from TWSE.",
        get_technical_indicators=(
            "Get moving averages (MA5/20/60), trend, period % change, "
            "average volume and momentum oscillators (RSI14, KD, MACD) "
            "for a Taiwan stock, computed from TWSE daily prices."
        ),
        get_institutional_flows="取得台股某檔最近交易日的三大法人(外資/投信/自營商)買賣超股數。",
        get_monthly_revenue="取得台股某檔最新月營收與年增率(YoY);若最新批次未涵蓋該股,會回報資料暫無。",
        get_risk_metrics="取得台股某檔的風險指標:年化波動率與最大回撤(由日收盤價計算)。",
        get_relative_strength=(
            "取得台股某檔相對大盤(加權指數)的表現:期間個股報酬率、大盤報酬率、"
            "超額報酬(excess_return_pct,>0 代表強於大盤)與 beta。"
        ),
        get_financials=(
            "取得台股某檔最新一季財報基本面:營收、毛利率、營業利益率、稅後淨利、"
            "ROE、EPS 與每股淨值;若最新批次未涵蓋該股,會回報資料暫無。"
        ),
        search_news="搜尋某主題的近期新聞標題與摘要(用於輿情分析)。",
    )


_TW_TEXT = {
    "eyebrow": "AI 投資委員會 · 個股研究報告",
    "title": "個股研究報告",
    "header_fallback": "台股個股分析",
    "generated_at": "產出時間",
    "rating": "投資評等", "confidence": "信心度", "last_close": "參考收盤",
    "thesis": "投資論點摘要", "dashboard": "關鍵數據儀表板",
    "chart": "近期股價走勢", "aspect": "分面分析",
    "risk": "風險與空方觀點", "integrity": "資料完整性查核",
    "integrity_support": "數據支持", "integrity_unsupported": "未獲數據支持(已標記)",
    "card_valuation": "估值", "row_pe": "本益比 (PE)", "row_pb": "股價淨值比 (PB)",
    "row_dy": "殖利率",
    "card_financials": "獲利能力", "row_gm": "毛利率", "row_om": "營業利益率",
    "row_roe": "ROE", "row_eps": "EPS",
    "card_technical": "技術指標", "row_close": "收盤", "row_ma20": "MA20",
    "row_rsi": "RSI14", "row_kd": "KD", "row_macd": "MACD", "row_chg": "期間漲跌",
    "card_relative": "相對大盤", "row_stock_ret": "個股報酬",
    "row_index_ret": "大盤報酬", "row_excess": "超額報酬", "row_beta": "Beta",
    "card_institutional": "三大法人(張)", "row_foreign": "外資", "row_trust": "投信",
    "row_dealer": "自營商", "row_total": "合計",
    "card_risk": "風險", "row_vol": "年化波動率", "row_mdd": "最大回撤",
    "card_revenue": "月營收", "row_rev": "當月營收", "row_yoy": "年增率 (YoY)",
    "row_mom": "月增率 (MoM)",
    "chart_caption": "收盤價 · MA20(虛線)", "chart_close": "收盤",
}


def tw_labels() -> ReportLabels:
    return ReportLabels(
        lang="zh-TW", text=_TW_TEXT,
        rating_class={"買進": "buy", "持有": "hold", "賣出": "sell"},
        recommend_label="建議", confidence_label="信心",
        agent_names={"fundamental": "基本面分析師", "technical": "技術面分析師",
                     "institutional": "籌碼面分析師", "news": "新聞輿情分析師",
                     "risk": "風險經理", "skeptic": "唱反調者", "chair": "主席",
                     "verifier": "查核員", "system": "系統"},
        phase_names={"RESEARCH": "研究分析", "CHALLENGE": "質詢", "REBUTTAL": "答辯",
                     "VERDICT": "最終結論", "REFLECT": "自我反省", "VERIFY": "自我查核"},
        aspect_order=[("fundamental", "基本面分析"), ("technical", "技術面分析"),
                      ("institutional", "籌碼面分析"), ("news", "新聞輿情分析")],
        institutional_kind="lots", revenue_kind="monthly",
        disclaimer=("免責聲明:本報告由 AI 投資委員會自動產生,所有數據取自公開資料來源(TWSE 等),"
                    "僅供研究與技術展示參考,不構成任何投資建議或要約。投資人應自行判斷並承擔風險。"))


def tw_ui() -> dict:
    return {
        "title": "台股投資委員會",
        "subtitle": "Agentic AI (7 位委員 + 自我查核)",
        "ticker_label": "股票代號:",
        "example_ticker": "2330",
        "run_button": "開始分析",
        "running_button": "分析中...",
        "idle": "● 閒置",
        "done_idle": "● 閒置 — 已完成",
        "pipeline_heading": "執行流程 Pipeline",
        "debate_heading": "即時討論 Live debate",
        "verdict_placeholder": "結論:(請先執行分析)",
        "verdict_prefix": "結論:",
        "verdict_running": "結論:分析 {stock} 中...",
        "verdict_done": "結論完成 ✓",
        "start_status": "開始分析 {stock} ...",
        "pending_badge": "⏳ 等待",
        "running_badge": "▶ 進行中",
        "done_badge": "✓ 完成",
        "thinking": "思考中",
        "writing": "撰寫中",
        "calling": "呼叫",
        "received": "已取得",
        "model_label": "模型: ",
        "tools_label": "工具: ",
        "tool_word": "工具",
        "done_word": "完成",
        "warn_word": "警告",
        "verify_prefix": "自我查核:數據支持",
        "unsupported_word": "未支持",
        "report_saved": "📄 報告已存",
        "open_report": "→ 開啟報告",
        "ws_error": "⚠ WebSocket 錯誤",
        "load_failed": "載入失敗: ",
        "recommend_word": "建議",
        "lean_words": ["看多", "看空", "中性"],
    }
