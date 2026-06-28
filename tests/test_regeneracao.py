"""A regeneracao anti-orfao deve reescrever GROUNDED a partir dos fatos das
ferramentas, nunca devolver vazio. Valida o mecanismo offline com FakeLLM.
"""

from __future__ import annotations

from bia_sentinela.harness.runtime import AgentHarness
from bia_sentinela.llm.base import LLMResponse, Message, ToolCall
from bia_sentinela.llm.fake import FakeLLM
from bia_sentinela.tools.base import ToolRegistry
from bia_sentinela.tools.example import ResumoGastosTool


def _responder(messages: list[Message]) -> LLMResponse:
    last = messages[-1]
    # 3a chamada: regeneracao. So produz grounded SE os fatos foram reapresentados.
    if last.role == "user" and "FATOS DAS FERRAMENTAS" in last.content:
        assert "162.55" in last.content  # o fato calculado chegou ao modelo
        return LLMResponse(text="No periodo, voce gastou R$ 162,55.", output_tokens=12)
    # 2a chamada: narra com numero ORFAO (nao veio de ferramenta).
    if last.role == "tool":
        return LLMResponse(text="Voce gastou R$ 9.999,00.", output_tokens=12)
    # 1a chamada: pede a ferramenta.
    return LLMResponse(
        text="",
        tool_calls=[
            ToolCall(id="t1", name="resumo_gastos", args={"transacoes": [-100.0, -50.25, -12.30]})
        ],
        output_tokens=8,
    )


def _harness() -> AgentHarness:
    tools = ToolRegistry()
    tools.register(ResumoGastosTool())
    return AgentHarness(
        FakeLLM(responder=_responder, model="fake"),
        tools,
        system_prompt="teste",
        regenerate_on_orphan=True,
    )


def test_regeneracao_reescreve_grounded_nao_vazio() -> None:
    res = _harness().run_turn("Quanto gastei?")
    assert not res.blocked
    assert res.response.strip()  # nao e vazio
    assert "162,55" in res.response
    assert res.verification and res.verification.ok
