from dataclasses import dataclass
from typing import Any, List

from agentcore.events import Event

# Domain-neutral default. The "{stock}" placeholder is just a subject identifier;
# the core stays free of any market/domain knowledge. Domains can override this via
# the Orchestrator's analyst_task_template (see committee/agents.py).
_DEFAULT_ANALYST_TASK = (
    "Analyze {stock} from your assigned perspective. Use your tools to gather real "
    "data first, then give your concise opinion and a BULLISH/BEARISH/NEUTRAL lean."
)


@dataclass
class Orchestrator:
    analysts: List[Any]
    chair: Any
    analyst_task_template: str = _DEFAULT_ANALYST_TASK

    def run(self, stock_no, llm, registry, bus, ledger) -> str:
        bus.emit(Event(type="phase", agent="system", data={"phase": "RESEARCH", "stock": stock_no}))
        statements = []
        for analyst in self.analysts:
            text = analyst.run(task=self.analyst_task_template.format(stock=stock_no), llm=llm,
                               registry=registry, bus=bus, ledger=ledger)
            statements.append((analyst.name, text))

        bus.emit(Event(type="phase", agent="system", data={"phase": "VERDICT", "stock": stock_no}))
        summary = "\n\n".join("[{}]\n{}".format(name, text) for name, text in statements)
        chair_task = (
            "Stock under review: {}. The committee analysts said:\n\n{}\n\n"
            "Now issue the committee's final recommendation."
        ).format(stock_no, summary)
        verdict = self.chair.run(task=chair_task, llm=llm, registry=registry,
                                 bus=bus, ledger=ledger)
        bus.emit(Event(type="verdict", agent=self.chair.name, data={"text": verdict}))
        return verdict
