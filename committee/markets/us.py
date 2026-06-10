# committee/markets/us.py
"""US market profile: English prompts, templates, tool descriptions, labels."""
from committee.markets.base import Prompts, Templates, ToolDescriptions, ReportLabels


def us_prompts() -> Prompts:
    return Prompts(
        fundamental=(
            "You are a fundamentals analyst covering US equities. Use get_valuation for "
            "P/E, P/B and dividend yield, get_monthly_revenue for the latest QUARTERLY "
            "revenue and YoY growth (US firms report quarterly), and get_financials for the "
            "latest gross margin, operating margin, ROE and EPS. Weigh valuation, "
            "profitability and growth together. Answer in English, concise (under 80 words), "
            "ending with a clear stance: Bullish, Bearish, or Neutral. Never fabricate "
            "numbers; if a tool fails or data is unavailable, say so plainly."),
        technical=(
            "You are a technical analyst covering US equities. Use get_technical_indicators "
            "for moving averages, trend, momentum and oscillators (RSI14, KD, MACD), and "
            "get_relative_strength for excess return vs the S&P 500 and beta. Judge trend, "
            "overbought/oversold, relative strength and entry timing. Answer in English, "
            "concise (under 80 words), ending with: Bullish, Bearish, or Neutral. Never "
            "fabricate numbers; if an indicator is null (insufficient data), say so."),
        institutional=(
            "You are an ownership/positioning analyst for US equities. Use "
            "get_institutional_flows for the institutional ownership percentage and the top "
            "institutional holders, and judge whether smart money is concentrated or light. "
            "Answer in English, concise (under 80 words), ending with: Bullish, Bearish, or "
            "Neutral. Never fabricate numbers."),
        news=(
            "You are a news/sentiment analyst for US equities. Use search_news to find "
            "recent company news and summarize bullish/bearish catalysts and market "
            "sentiment. Answer in English, concise (under 80 words), ending with: Bullish, "
            "Bearish, or Neutral. Cite only what appears in the news; invent nothing."),
        risk=(
            "You are the committee's risk manager. Use get_risk_metrics for annualized "
            "volatility and max drawdown, assess downside risk, and challenge any analyst "
            "who is too optimistic. Answer in English, concise (under 80 words). Never "
            "fabricate numbers."),
        skeptic=(
            "You are the committee's devil's advocate, with no tools. Challenge the emerging "
            "consensus, expose weaknesses and blind spots, and guard against groupthink. In "
            "English, give 2-3 sharp, specific counterarguments (under 80 words)."),
        chair=(
            "You are the committee chair. You receive each member's view and their "
            "challenges and rebuttals, and must deliver a single final verdict. Respond "
            "entirely in English and STRICTLY in this format: first line "
            "'Recommendation: BUY|HOLD|SELL' (choose one), second line 'Confidence: NN%', "
            "then a paragraph of reasoning citing members' points. Use no numbers beyond "
            "those members provided; fabricate nothing."),
        verifier=(
            "You are the committee's verifier. You see the chair's verdict and the figures "
            "members cited. In English, check the verdict is consistent with the actual "
            "data and the reasoning is sound, and flag anything unsupported or "
            "contradictory. If all consistent, reply 'VERIFIED'; otherwise list the issues."),
    )


def us_templates() -> Templates:
    return Templates(
        analyst=("Analyze US stock {stock} from your area of expertise. First use your "
                 "tools to gather real data, then give a concise view ending with a "
                 "Bullish/Bearish/Neutral stance."),
        challenge=("Below are the analysts' views on US stock {stock}. From your angle, "
                   "raise challenges and risks, attacking points that are too optimistic "
                   "or weakly evidenced."),
        rebuttal=("The risk manager and skeptic raised the above challenges. Responding "
                  "only where it concerns your expertise, reply or revise your earlier "
                  "view on US stock {stock} in one paragraph."),
        reflect=("Below is your draft verdict on US stock {stock}. Re-examine your "
                 "reasoning: are the points solid, internally consistent, and is every "
                 "figure supported by data members cited? Fix any problems, then OUTPUT "
                 "ONLY the improved final recommendation in the exact original format "
                 "(first line 'Recommendation: BUY|HOLD|SELL', second line 'Confidence: "
                 "NN%', then reasoning); add nothing outside the format and invent no "
                 "new numbers."),
        verify=("Check whether the committee's verdict on US stock {stock} is consistent "
                "with the figures members cited; flag any unsupported number or "
                "contradiction. If there are none, reply 'VERIFIED'."),
        correction=("Verification found these figures unsupported by data: {figures}. "
                    "Revise the recommendation on US stock {stock} using only "
                    "data-supported numbers, keeping the original output format."),
        discussion=("Here is the committee discussion so far. From your perspective, "
                    "challenge the points you disagree with and defend or revise your view "
                    "on US stock {stock} in one short paragraph. Cite only figures your "
                    "tools returned; never invent numbers."),
    )


def us_tool_descriptions() -> ToolDescriptions:
    return ToolDescriptions(
        stock_param="US stock ticker, e.g. AAPL",
        get_valuation="Get P/E, P/B and dividend yield for a US stock (Yahoo Finance).",
        get_technical_indicators=("Get moving averages (MA5/20/60), trend, period % change, "
                                  "average volume and momentum oscillators (RSI14, KD, MACD) "
                                  "for a US stock, computed from daily prices."),
        get_institutional_flows=("Get the institutional ownership percentage and top "
                                 "institutional holders for a US stock."),
        get_monthly_revenue=("Get a US stock's latest QUARTERLY revenue and YoY growth "
                             "(US firms report quarterly, not monthly); reports unavailable "
                             "if data is missing."),
        get_risk_metrics="Get a US stock's risk metrics: annualized volatility and max drawdown.",
        get_relative_strength=("Get a US stock's performance vs the S&P 500: stock return, "
                               "index return, excess_return_pct (>0 means stronger than the "
                               "market) and beta."),
        get_financials=("Get a US stock's latest-quarter fundamentals from SEC filings: "
                        "revenue, gross/operating margin, net income, ROE and EPS; reports "
                        "unavailable if not in EDGAR."),
        search_news="Search recent news headlines and snippets for a topic (for sentiment).",
    )


_US_TEXT = {
    "eyebrow": "AI Investment Committee · Equity Research",
    "title": "Equity Research Report", "header_fallback": "US Equity Analysis",
    "generated_at": "Generated", "rating": "Rating", "confidence": "Confidence",
    "last_close": "Last Close", "thesis": "Investment Thesis",
    "dashboard": "Key Data Dashboard", "chart": "Recent Price Trend",
    "aspect": "Aspect Analysis", "risk": "Risks & Bear Case",
    "integrity": "Data Integrity Check", "integrity_support": "Figures supported",
    "integrity_unsupported": "Unsupported (flagged)",
    "card_valuation": "Valuation", "row_pe": "P/E", "row_pb": "P/B", "row_dy": "Dividend Yield",
    "card_financials": "Profitability", "row_gm": "Gross Margin", "row_om": "Operating Margin",
    "row_roe": "ROE", "row_eps": "EPS",
    "card_technical": "Technicals", "row_close": "Close", "row_ma20": "MA20",
    "row_rsi": "RSI14", "row_kd": "KD", "row_macd": "MACD", "row_chg": "Period Change",
    "card_relative": "vs S&P 500", "row_stock_ret": "Stock Return",
    "row_index_ret": "Index Return", "row_excess": "Excess Return", "row_beta": "Beta",
    "card_institutional": "Institutional Ownership", "row_inst_own": "Institutional %",
    "card_risk": "Risk", "row_vol": "Annualized Volatility", "row_mdd": "Max Drawdown",
    "card_revenue": "Quarterly Revenue", "row_rev": "Revenue", "row_yoy": "YoY",
    "chart_caption": "Close · MA20 (dashed)", "chart_close": "Close",
    "row_foreign": "", "row_trust": "", "row_dealer": "", "row_total": "", "row_mom": "",
    "thinking_label": "Thinking",
    "unverified_label": "unverified figure",
}


def us_labels() -> ReportLabels:
    return ReportLabels(
        lang="en", text=_US_TEXT,
        rating_class={"BUY": "buy", "HOLD": "hold", "SELL": "sell"},
        recommend_label="Recommendation", confidence_label="Confidence",
        agent_names={"fundamental": "Fundamentals Analyst", "technical": "Technical Analyst",
                     "institutional": "Ownership Analyst", "news": "News Analyst",
                     "risk": "Risk Manager", "skeptic": "Skeptic", "chair": "Chair",
                     "verifier": "Verifier", "system": "System"},
        phase_names={"RESEARCH": "Research", "CHALLENGE": "Challenge", "REBUTTAL": "Rebuttal",
                     "DISCUSSION": "Discussion",
                     "VERDICT": "Verdict", "REFLECT": "Reflect", "VERIFY": "Verify"},
        aspect_order=[("fundamental", "Fundamentals"), ("technical", "Technicals"),
                      ("institutional", "Ownership"), ("news", "News & Sentiment")],
        institutional_kind="ownership", revenue_kind="quarterly",
        disclaimer=("Disclaimer: This report is generated automatically by an AI investment "
                    "committee. All figures come from public sources (Yahoo Finance, SEC "
                    "EDGAR) and are for research and demonstration only — not investment "
                    "advice. Invest at your own risk."))


def us_ui() -> dict:
    return {
        "title": "US Equity Investment Committee",
        "subtitle": "Agentic AI (7 members + self-check)",
        "ticker_label": "Ticker:",
        "example_ticker": "AAPL",
        "run_button": "Analyze",
        "running_button": "Analyzing...",
        "idle": "● Idle",
        "done_idle": "● Idle — finished",
        "pipeline_heading": "Pipeline",
        "debate_heading": "Live Debate",
        "verdict_placeholder": "Verdict: (run an analysis first)",
        "verdict_prefix": "Verdict: ",
        "verdict_running": "Verdict: analyzing {stock} ...",
        "verdict_done": "Verdict ready ✓",
        "start_status": "Analyzing {stock} ...",
        "pending_badge": "⏳ waiting",
        "running_badge": "▶ running",
        "done_badge": "✓ done",
        "thinking": "thinking",
        "writing": "writing",
        "calling": "calling",
        "received": "received",
        "model_label": "Model: ",
        "tools_label": "Tools: ",
        "tool_word": "tool",
        "done_word": "done",
        "warn_word": "warning",
        "verify_prefix": "Self-check: figures supported",
        "unsupported_word": "unsupported",
        "report_saved": "📄 Report saved",
        "open_report": "→ Open report",
        "ws_error": "⚠ WebSocket error",
        "load_failed": "Load failed: ",
        "recommend_word": "Recommendation",
        "lean_words": ["Bullish", "Bearish", "Neutral"],
        "thinking_label": "Thinking",
        "others_label": "Others (enter code)",
        "unverified_label": "unverified figure",
    }


def us_stocklist() -> list:
    def cat(label, *pairs):
        return {"label": label, "items": [{"code": c, "name": n} for c, n in pairs]}
    return [
        cat("CPU", ("INTC", "Intel"), ("AMD", "AMD"), ("ARM", "Arm Holdings"),
            ("QCOM", "Qualcomm")),
        cat("GPU / AI Accelerators", ("NVDA", "NVIDIA"), ("AMD", "AMD"),
            ("AVGO", "Broadcom"), ("MRVL", "Marvell")),
        cat("Memory & Storage", ("MU", "Micron"), ("WDC", "Western Digital"),
            ("STX", "Seagate"), ("SNDK", "SanDisk"), ("SIMO", "Silicon Motion")),
        cat("Semiconductor Equipment", ("ASML", "ASML"), ("AMAT", "Applied Materials"),
            ("LRCX", "Lam Research"), ("KLAC", "KLA"), ("TER", "Teradyne")),
        cat("EDA", ("SNPS", "Synopsys"), ("CDNS", "Cadence")),
        cat("Software (Enterprise & Security)", ("MSFT", "Microsoft"), ("ORCL", "Oracle"),
            ("ADBE", "Adobe"), ("CRM", "Salesforce"), ("NOW", "ServiceNow"),
            ("INTU", "Intuit"), ("PANW", "Palo Alto Networks"), ("CRWD", "CrowdStrike")),
        cat("AI & Data Software", ("PLTR", "Palantir"), ("SNOW", "Snowflake"),
            ("DDOG", "Datadog"), ("NET", "Cloudflare"), ("MDB", "MongoDB")),
        cat("AI Infrastructure / Servers", ("SMCI", "Super Micro"), ("DELL", "Dell"),
            ("HPE", "HPE"), ("ANET", "Arista"), ("VRT", "Vertiv")),
        cat("Internet & Cloud", ("GOOGL", "Alphabet"), ("AMZN", "Amazon"),
            ("META", "Meta"), ("NFLX", "Netflix"), ("UBER", "Uber")),
        cat("Devices & Networking", ("AAPL", "Apple"), ("CSCO", "Cisco"),
            ("MSI", "Motorola Solutions"), ("JNPR", "Juniper")),
        cat("EV & Autonomous", ("TSLA", "Tesla"), ("RIVN", "Rivian"),
            ("LCID", "Lucid"), ("MBLY", "Mobileye")),
    ]
