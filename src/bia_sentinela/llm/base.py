"""Interface de LLM independente de provedor.

O harness depende deste Protocol, não da SDK: `FakeLLM` em teste/eval offline,
`AnthropicLLM` em produção.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Message:
    role: str  # "user" | "assistant" | "tool"
    content: str
    tool_call_id: str | None = None  # quando role == "tool"


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = "unknown"
    raw: dict[str, Any] | None = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[Message],
        *,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse: ...
