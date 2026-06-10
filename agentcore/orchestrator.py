from dataclasses import dataclass
from typing import Any, List, Tuple

from agentcore.events import Event
from agentcore.verify import check_grounding

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
_DEFAULT_DISCUSSION_TASK = (
    "Here is the committee discussion so far. From your perspective, challenge the "
    "points you disagree with and defend or revise your own view on {stock}, in one "
    "short paragraph. Cite only figures supported by the data your tools returned; "
    "never invent numbers."
)
_DEFAULT_REFLECT_TASK = (
    "Re-examine your own draft recommendation for {stock} shown above. Check whether "
    "your reasoning is sound, internally consistent, and supported by the cited data. "
    "Then output an improved final recommendation in the EXACT same format; do not add "
    "any commentary outside that format."
)
_DEFAULT_VERIFY_TASK = (
    "Review the committee's verdict on {stock} against the data the analysts cited. "
    "Flag any figure not supported by the data, or any internal inconsistency; be concise."
)
_DEFAULT_CORRECTION_TASK = (
    "Verification flagged these figures as unsupported by the recorded data: {figures}. "
    "Revise the recommendation for {stock} using only supported figures, keeping the "
    "exact same output format."
)


def _join(items: List[Tuple[str, str]]) -> str:
    return "\n\n".join("[{}]\n{}".format(name, text) for name, text in items)


@dataclass
class Orchestrator:
    """Runs a Chair-led, bounded debate: RESEARCH -> CHALLENGE -> REBUTTAL -> VERDICT
    -> (optional REFLECT) -> (optional VERIFY).

    Domain-agnostic: it only sequences groups of agents and passes prior statements
    forward as context. Task wording is injected via the templates.
    """
    research: List[Any]
    challengers: List[Any]
    chair: Any
    analyst_task_template: str = _DEFAULT_ANALYST_TASK
    challenge_task_template: str = _DEFAULT_CHALLENGE_TASK
    rebuttal_task_template: str = _DEFAULT_REBUTTAL_TASK
    discussion_rounds: int = 0          # 0 = off (scripted challenge/rebuttal); N = round-robin debate
    discussion_task_template: str = _DEFAULT_DISCUSSION_TASK
    reflect_task_template: str = _DEFAULT_REFLECT_TASK
    reflection_passes: int = 0          # 0 = off; Chair self-refines its draft N times
    verifier: Any = None
    verify_task_template: str = _DEFAULT_VERIFY_TASK
    correction_task_template: str = _DEFAULT_CORRECTION_TASK

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

        if self.discussion_rounds > 0:
            phase("DISCUSSION")
            debaters = list(self.research) + list(self.challengers)
            for _ in range(self.discussion_rounds):
                for a in debaters:
                    text = run_agent(a, self.discussion_task_template.format(stock=stock_no),
                                     context=_join(transcript))
                    transcript.append((a.name, text))
                    g = check_grounding(text, ledger)
                    if not g["grounded"]:
                        bus.emit(Event(type="grounding_flag", agent=a.name,
                                       data={"unsupported": g["unsupported"]}))
        else:
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

        # REFLECT: optional Chair self-refinement of its own draft, before VERIFY.
        # Each pass feeds the current verdict back as context; the Chair must return an
        # improved verdict in the same format (no free-form critique outside it).
        reflected = False
        if self.reflection_passes > 0:
            phase("REFLECT")
            for _ in range(self.reflection_passes):
                verdict = run_agent(self.chair,
                                    self.reflect_task_template.format(stock=stock_no),
                                    context=verdict)
                reflected = True

        verdict_data = {"text": verdict}
        if reflected:
            verdict_data["reflected"] = True
        bus.emit(Event(type="verdict", agent=self.chair.name, data=verdict_data))

        if self.verifier is None:
            return verdict

        # VERIFY: deterministic grounding check + an LLM consistency pass, then one
        # bounded correction round. Unsupported figures are flagged, never hidden.
        phase("VERIFY")
        grounding = check_grounding(verdict, ledger)
        bus.emit(Event(type="verification", agent=self.verifier.name,
                       data={"grounding": grounding}))
        run_agent(self.verifier, self.verify_task_template.format(stock=stock_no),
                  context=verdict)
        if not grounding["grounded"]:
            figures = ", ".join(str(x) for x in grounding["unsupported"])
            verdict = run_agent(self.chair,
                                self.correction_task_template.format(stock=stock_no,
                                                                     figures=figures),
                                context=verdict)
            bus.emit(Event(type="verdict", agent=self.chair.name,
                           data={"text": verdict, "corrected": True}))
            grounding = check_grounding(verdict, ledger)
            bus.emit(Event(type="verification", agent=self.verifier.name,
                           data={"grounding": grounding, "final": True}))
        return verdict
