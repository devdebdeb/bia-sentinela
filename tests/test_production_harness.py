"""Valida a fiacao do harness de PRODUCAO (ferramentas reais + politica de
suitability) offline, injetando um FakeLLM no lugar do AnthropicLLM. Nao usa
rede nem chave: prova o MECANISMO, nao a qualidade de um modelo real.
"""

from __future__ import annotations

import re

import pytest

from bia_sentinela.harness.factory import build_production_harness
from bia_sentinela.llm.base import LLMResponse, Message, ToolCall

pytest.importorskip("sklearn")  # detectar_anomalias depende do extra [ml]

from config.settings import Settings  # noqa: E402


def _responder(messages: list[Message]) -> LLMResponse:
    last = messages[-1]
    if last.role == "tool":
        if "detectar_anomalias" in last.content:
            m = re.search(r'"numeros":\s*\[\s*([0-9.]+)', last.content)
            val = m.group(1) if m else "0"
            return LLMResponse(
                text=f"Notei uma movimentacao atipica de R$ {val}.", output_tokens=20
            )
        if "avaliar_suitability" in last.content:
            # Recomenda de proposito um produto BLOQUEADO (fora do elegivel).
            return LLMResponse(text="Recomendo o Fundo Cripto para voce.", output_tokens=12)
        return LLMResponse(text="Certo.", output_tokens=4)

    texto = last.content.lower()
    if "estranho" in texto or "anomal" in texto:
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="a1", name="detectar_anomalias", args={"top_n": 5})],
            output_tokens=8,
        )
    if "invest" in texto or "recomend" in texto:
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="s1", name="avaliar_suitability", args={})],
            output_tokens=8,
        )
    return LLMResponse(text="Como posso ajudar com suas financas?", output_tokens=8)


def _harness():  # noqa: ANN202
    from bia_sentinela.llm.fake import FakeLLM

    fake = FakeLLM(responder=_responder, model="fake-prod")
    # settings com chave None: garante que so o llm injetado e usado.
    return build_production_harness(settings=Settings(anthropic_api_key=None), llm=fake)


def test_anomalia_e_grounded() -> None:
    res = _harness().run_turn("tem algum gasto estranho nas minhas contas?")
    assert not res.blocked
    assert res.verification and res.verification.ok
    assert any(tc.name == "detectar_anomalias" for tc in res.tool_calls)


def test_suitability_bloqueia_produto_fora_do_elegivel() -> None:
    res = _harness().run_turn("onde devo investir meu dinheiro?")
    # O perfil e moderado: Fundo Cripto (arrojado) nao e elegivel -> gate barra.
    assert res.blocked
    assert res.block_reason == "policy_violation"


def test_sem_chave_e_sem_llm_injetado_falha_claramente() -> None:
    # Default = provedor openai (Groq); sem chave o erro aponta a variavel certa.
    s = Settings(llm_provider="openai", openai_api_key=None)
    with pytest.raises(RuntimeError, match="BIA_OPENAI_API_KEY"):
        build_production_harness(settings=s)


def test_seletor_de_provedor_anthropic_sem_chave() -> None:
    from bia_sentinela.harness.factory import build_llm

    s = Settings(llm_provider="anthropic", anthropic_api_key=None)
    with pytest.raises(RuntimeError, match="BIA_ANTHROPIC_API_KEY"):
        build_llm(s)
