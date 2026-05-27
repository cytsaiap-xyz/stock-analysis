from dataclasses import dataclass
from typing import Any, List, Tuple

from agentcore.events import Event

# Domain-neutral defaults. "{stock}" is just a subject identifier; the core holds
# no market/domain knowledge. Domains override these (see committee/agents.py).
_DEFAULT_ANALYST_TASK = (
    "Analyze {stock} from your assigned perspective. Use your tools to gather real "
    "data first, then give your concise opinion and a BULLISH/BEARISH/NEUTRAL lean."
)
_DEFAULT_CHALLENGE_TASK = (
    "Read the analysts' statements about {stock} and challenge the weakest, most "
    "over-optimistic or least-supported points from your perspective."
)
_DEFAULT_REBUTTAL_TASK = (
    "The challengers raised the points above. In one paragraph, respond to those "
    "relevant to your expertise or revise your earlier view on {stock}."
)


def _join(items: List[Tuple[str, str]]) -> str:
    return "\n\n".join("[{}]\n{}".format(name, text) for name, text in items)


@dataclass
class Orchestrator:
    """Runs a Chair-led, bounded debate: RESEARCH -> CHALLENGE -> REBUTTAL -> VERDICT.

    Domain-agnostic: it only sequences groups of agents and passes prior statements
    forward as context. Task wording is injected via the templates.
    """
    research: List[Any]
    challengers: List[Any]
    chair: Any
    analyst_task_template: str = _DEFAULT_ANALYST_TASK
    challenge_task_template: str = _DEFAULT_CHALLENGE_TASK
    rebuttal_task_template: str = _DEFAULT_REBUTTAL_TASK

    def run(self, stock_no, llm, registry, bus, ledger) -> str:
        def phase(name: str) -> None:
            bus.emit(Event(type="phase", agent="system",
                           data={"phase": name, "stock": stock_no}))

        def run_agent(agent, task, context=""):
            return agent.run(task=task, llm=llm, registry=registry,
                             bus=bus, ledger=ledger, context=context)

        transcript: List[Tuple[str, str]] = []

        phase("RESEARCH")
        for a in self.research:
            text = run_agent(a, self.analyst_task_template.format(stock=stock_no))
            transcript.append((a.name, text))

        phase("CHALLENGE")
        research_summary = _join(transcript)
        challenger_names = set()
        for c in self.challengers:
            challenger_names.add(c.name)
            text = run_agent(c, self.challenge_task_template.format(stock=stock_no),
                             context=research_summary)
            transcript.append((c.name, text))

        phase("REBUTTAL")
        challenge_summary = _join([t for t in transcript if t[0] in challenger_names])
        for a in self.research:
            text = run_agent(a, self.rebuttal_task_template.format(stock=stock_no),
                             context=challenge_summary)
            transcript.append((a.name + " (答辯)", text))

        phase("VERDICT")
        chair_task = (
            "Stock under review: {}. Full committee discussion:\n\n{}\n\n"
            "Now issue the committee's final recommendation."
        ).format(stock_no, _join(transcript))
        verdict = run_agent(self.chair, chair_task)
        bus.emit(Event(type="verdict", agent=self.chair.name, data={"text": verdict}))
        return verdict
