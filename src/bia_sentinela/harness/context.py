"""Contexto de execução de um turno.

Carrega o `trace_id`, o logger correlacionado, o acumulador de custo/tokens e
fixa a seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..observability.logging import TraceLogger
from ..schemas import LLMUsage, ToolCallRecord, new_trace_id


@dataclass
class RunContext:
    trace_id: str
    logger: TraceLogger
    seed: int
    usage: list[LLMUsage] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)

    @classmethod
    def new(cls, seed: int) -> RunContext:
        tid = new_trace_id()
        random.seed(seed)  # determinismo de qualquer componente estocástico
        return cls(trace_id=tid, logger=TraceLogger(tid), seed=seed)

    def record_usage(self, usage: LLMUsage) -> None:
        self.usage.append(usage)

    def record_tool(self, rec: ToolCallRecord) -> None:
        self.tool_calls.append(rec)
