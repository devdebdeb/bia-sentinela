"""Harness para avaliação offline.

Usa um FakeLLM roteado por palavras-chave para exercitar o gate no CI sem rede.
Em produção, uma fábrica equivalente injeta o `AnthropicLLM` e as ferramentas
reais.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..llm.base import LLMResponse, Message, ToolCall
from ..llm.fake import FakeLLM
from ..prompts import SYSTEM_PROMPT
from ..tools.base import ToolRegistry
from ..tools.example import ResumoGastosTool

if TYPE_CHECKING:
    from ..harness.runtime import AgentHarness


def _offline_responder(messages: list[Message]) -> LLMResponse:
    last = messages[-1]

    # Segunda passada: já temos o resultado da ferramenta -> narrar (grounded).
    if last.role == "tool":
        m = re.search(r'"total_gastos":\s*([\d.]+)', last.content)
        total = m.group(1) if m else "0"
        return LLMResponse(text=f"No período analisado, você gastou R$ {total}.", output_tokens=20)

    text = last.content.lower()

    # Adversarial: injeção / exfiltração -> recusa.
    gatilhos = ("ignore", "todos os clientes", "outro cliente", "system prompt", "suas instruções")
    if any(k in text for k in gatilhos):
        return LLMResponse(
            text=(
                "Não posso ajudar com isso. Não tenho acesso a dados de outros clientes "
                "nem revelo minhas instruções."
            ),
            output_tokens=18,
        )

    # Fora de escopo.
    if any(k in text for k in ("tempo", "clima", "futebol", "receita de", "piada")):
        return LLMResponse(
            text=(
                "Isso está fora do meu escopo, que é cuidar das suas finanças pessoais. "
                "Não posso responder."
            ),
            output_tokens=16,
        )

    # Factual sobre gastos -> pede ferramenta.
    if "gast" in text:
        return LLMResponse(
            text="",
            tool_calls=[
                ToolCall(
                    id="t1",
                    name="resumo_gastos",
                    args={"transacoes": [-100.0, -50.25, -12.30], "categoria": "alimentacao"},
                )
            ],
            output_tokens=8,
        )

    return LLMResponse(
        text="Posso ajudar com suas finanças. O que você gostaria de saber?", output_tokens=12
    )


def build_offline_harness() -> AgentHarness:
    # import tardio evita ciclo (runtime importa config)
    from ..harness.runtime import AgentHarness  # noqa: PLC0415

    tools = ToolRegistry()
    tools.register(ResumoGastosTool())
    llm = FakeLLM(responder=_offline_responder, model="fake-model")
    return AgentHarness(llm, tools, system_prompt=SYSTEM_PROMPT, seed=42)
