from dataclasses import dataclass
from typing import List

from agentcore.agent import Agent
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER

_FUNDAMENTAL_PROMPT = (
    "你是一位專注台股的基本面分析師。請使用 get_valuation 取得本益比、股價淨值比與"
    "殖利率,get_monthly_revenue 取得最新月營收年增率,並用 get_financials 取得最新一季"
    "毛利率、營業利益率、ROE 與 EPS,綜合判斷估值、獲利能力與成長性。"
    "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
    "切勿捏造數字;若工具失敗或資料暫無,請直接說明。"
)

_TECHNICAL_PROMPT = (
    "你是一位專注台股的技術面分析師。請使用 get_technical_indicators 取得均線、趨勢、"
    "動能與震盪指標(RSI14、KD、MACD),並用 get_relative_strength 取得相對大盤的超額"
    "報酬與 beta,綜合判斷趨勢、超買超賣、相對強弱與進場時機。"
    "請以繁體中文、精簡作答(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
    "切勿捏造數字;若工具失敗或某指標為 null(資料不足),請直接說明,不要臆測。"
)

_INSTITUTIONAL_PROMPT = (
    "你是一位專注台股的籌碼面分析師。請使用 get_institutional_flows 取得三大法人"
    "(外資/投信/自營商)買賣超,判斷主力資金是進場或出場。請以繁體中文、精簡作答"
    "(120字以內),最後以明確傾向作結:看多、看空 或 中性。切勿捏造數字。"
)

_NEWS_PROMPT = (
    "你是一位專注台股的新聞輿情分析師。請使用 search_news 搜尋該公司的近期新聞,"
    "歸納利多/利空與市場情緒。請以繁體中文、精簡作答(120字以內),最後以明確傾向"
    "作結:看多、看空 或 中性。僅引用新聞重點,不要捏造未出現的內容。"
)

_RISK_PROMPT = (
    "你是投資委員會的風險經理。請使用 get_risk_metrics 取得年化波動率與最大回撤,"
    "評估下檔風險,並對其他分析師過於樂觀之處提出質疑。請以繁體中文、精簡作答"
    "(120字以內)。切勿捏造數字。"
)

_SKEPTIC_PROMPT = (
    "你是委員會的唱反調者(魔鬼代言人),沒有任何工具。你的任務是挑戰目前浮現的"
    "共識、找出論點的弱點與盲點,避免團體迷思。請以繁體中文、犀利但具體地提出"
    "2-3 個反對理由(120字以內)。"
)

_CHAIR_PROMPT = (
    "你是投資委員會的主席。你會收到各委員的意見與彼此的質詢答辯,必須做出單一的"
    "最終結論。請完全以繁體中文,並嚴格依下列格式輸出:第一行「建議: 買進｜持有｜賣出」"
    "(三擇一),第二行「信心: NN%」,接著一段引用各委員論點的理由。除委員提供的"
    "數字外,不得自行捏造數字。"
)

_VERIFIER_PROMPT = (
    "你是委員會的查核員。你會看到主席的結論與委員引用的數據。請以繁體中文檢查結論"
    "是否與實際數據一致、推理是否合理,並指出任何沒有數據支持或前後矛盾之處。"
    "若全部一致,請回覆『查核通過』;否則簡要列出問題。"
)

# Domain-specific task wording, passed into the (domain-neutral) Orchestrator.
ANALYST_TASK_TEMPLATE = (
    "請從你的專業角度分析台股 {stock}。請先使用你的工具取得真實資料,"
    "再給出精簡看法,並以 看多/看空/中性 的傾向作結。"
)
CHALLENGE_TASK_TEMPLATE = (
    "以下是各分析師對台股 {stock} 的意見。請從你的角度提出質疑與風險,"
    "挑戰其中過於樂觀或證據不足的論點。"
)
REBUTTAL_TASK_TEMPLATE = (
    "風險經理與唱反調者提出了上述質疑。請針對與你專業相關的部分,"
    "用一段話回應或修正你先前對台股 {stock} 的看法。"
)
VERIFY_TASK_TEMPLATE = (
    "請檢視委員會對台股 {stock} 的結論是否與各委員引用的數據一致,"
    "指出任何沒有數據支持的數字或前後矛盾之處;若無問題請回覆「查核通過」。"
)
CORRECTION_TASK_TEMPLATE = (
    "查核發現以下數字未獲數據支持:{figures}。請重新修正對台股 {stock} 的建議,"
    "只使用有數據支持的數字,並維持原本的輸出格式。"
)


@dataclass
class Committee:
    research: List[Agent]      # fundamental, technical, institutional, news
    challengers: List[Agent]   # risk, skeptic
    chair: Agent
    verifier: Agent


def build_committee() -> Committee:
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=_FUNDAMENTAL_PROMPT, model=MODEL_TOOL_CALLER,
                        tool_names=["get_valuation", "get_monthly_revenue",
                                    "get_financials"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=_TECHNICAL_PROMPT, model=MODEL_TOOL_CALLER,
                      tool_names=["get_technical_indicators", "get_relative_strength"])
    institutional = Agent(name="institutional", role="Institutional Flow Analyst",
                          system_prompt=_INSTITUTIONAL_PROMPT, model=MODEL_TOOL_CALLER,
                          tool_names=["get_institutional_flows"])
    news = Agent(name="news", role="News Analyst",
                 system_prompt=_NEWS_PROMPT, model=MODEL_TOOL_CALLER,
                 tool_names=["search_news"])
    risk = Agent(name="risk", role="Risk Manager",
                 system_prompt=_RISK_PROMPT, model=MODEL_REASONER,
                 tool_names=["get_risk_metrics"])
    skeptic = Agent(name="skeptic", role="Skeptic",
                    system_prompt=_SKEPTIC_PROMPT, model=MODEL_REASONER, tool_names=[])
    chair = Agent(name="chair", role="Chair",
                  system_prompt=_CHAIR_PROMPT, model=MODEL_REASONER, tool_names=[])
    verifier = Agent(name="verifier", role="Verifier",
                     system_prompt=_VERIFIER_PROMPT, model=MODEL_REASONER, tool_names=[])
    return Committee(research=[fundamental, technical, institutional, news],
                     challengers=[risk, skeptic], chair=chair, verifier=verifier)
