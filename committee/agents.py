from typing import List, Tuple

from agentcore.agent import Agent
from committee.config import MODEL_REASONER, MODEL_TOOL_CALLER

_FUNDAMENTAL_PROMPT = (
    "你是一位專注台股的基本面分析師。請使用 get_valuation 取得真實的本益比、"
    "股價淨值比與殖利率,判斷目前估值是否具吸引力。請以繁體中文、精簡作答"
    "(120字以內),最後以明確傾向作結:看多、看空 或 中性。"
    "切勿捏造數字;若工具失敗,請直接說明資料無法取得。"
)

_TECHNICAL_PROMPT = (
    "你是一位專注台股的技術面分析師。請使用 get_technical_indicators 取得均線、"
    "趨勢與動能,評估趨勢與進場時機。請以繁體中文、精簡作答(120字以內),"
    "最後以明確傾向作結:看多、看空 或 中性。"
    "切勿捏造數字;若工具失敗,請直接說明資料無法取得。"
)

# Domain-specific analyst task wording, passed into the (domain-neutral) Orchestrator.
ANALYST_TASK_TEMPLATE = (
    "請從你的專業角度分析台股 {stock}。請先使用你的工具取得真實資料,"
    "再給出精簡看法,並以 看多/看空/中性 的傾向作結。"
)

_CHAIR_PROMPT = (
    "你是投資委員會的主席。你會收到各分析師的意見,必須做出單一的最終結論。"
    "請完全以繁體中文,並嚴格依下列格式輸出:第一行「建議: 買進｜持有｜賣出」"
    "(三擇一),第二行「信心: NN%」,接著一段引用各分析師論點的理由。"
    "除分析師提供的數字外,不得自行捏造數字。"
)


def build_committee() -> Tuple[List[Agent], Agent]:
    fundamental = Agent(name="fundamental", role="Fundamental Analyst",
                        system_prompt=_FUNDAMENTAL_PROMPT, model=MODEL_TOOL_CALLER,
                        tool_names=["get_valuation"])
    technical = Agent(name="technical", role="Technical Analyst",
                      system_prompt=_TECHNICAL_PROMPT, model=MODEL_TOOL_CALLER,
                      tool_names=["get_technical_indicators"])
    chair = Agent(name="chair", role="Chair", system_prompt=_CHAIR_PROMPT,
                  model=MODEL_REASONER, tool_names=[])
    return [fundamental, technical], chair
