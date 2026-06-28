"""Fábrica de harness de produção.

Espelho de `build_offline_harness`, mas monta o agente com as FERRAMENTAS REAIS
(anomalias, suitability, metas) e, por padrao, o `AnthropicLLM` atras da chave de
ambiente. A `SuitabilityRule` e plugada com o catalogo real, tornando o gate de
suitability efetivo.

O LLM e injetavel (`llm=`): em producao usa o real; em teste/demo um `FakeLLM`
exercita a MESMA fiacao (ferramentas + politica) sem rede nem chave.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from config.settings import Settings, get_settings

from ..data.ingestion import (
    carregar_glossario,
    carregar_perfil,
    carregar_produtos,
    carregar_transacoes,
)
from ..guardrails.policy import PolicyGate, PromessasProibidasRule, SuitabilityRule
from ..prompts import SYSTEM_PROMPT
from ..tools.build import build_registry

if TYPE_CHECKING:
    from ..llm.base import LLMClient
    from .runtime import AgentHarness


def build_llm(settings: Settings) -> LLMClient:
    """Seleciona o cliente de LLM conforme `llm_provider`.

    'openai' cobre qualquer endpoint compativel (Groq, Gemini, Ollama,
    OpenRouter); 'anthropic' usa a SDK paga. A chave vem sempre do ambiente.
    """
    provider = (settings.llm_provider or "").lower()
    if provider in {"openai", "groq", "gemini", "ollama", "local", "openrouter"}:
        if not settings.openai_api_key:
            raise RuntimeError(
                "BIA_OPENAI_API_KEY ausente. Defina a chave do provedor no ambiente "
                "(.env). Para Ollama local use qualquer valor nao-vazio (ex.: 'ollama')."
            )
        from ..llm.openai_compat import OpenAICompatLLM  # noqa: PLC0415

        return OpenAICompatLLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
            max_tokens=settings.max_tokens,
            timeout_s=settings.request_timeout_s,
            max_retries=settings.max_retries,
            temperature=settings.temperature,
        )
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("BIA_ANTHROPIC_API_KEY ausente no ambiente (.env).")
        from ..llm.anthropic_client import AnthropicLLM  # noqa: PLC0415

        return AnthropicLLM(
            api_key=settings.anthropic_api_key,
            model=settings.model,
            max_tokens=settings.max_tokens,
            timeout_s=settings.request_timeout_s,
            max_retries=settings.max_retries,
        )
    raise RuntimeError(f"llm_provider desconhecido: '{settings.llm_provider}'")


def build_production_harness(
    *,
    data_dir: str | Path = "data/raw",
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    dio: bool = False,
) -> AgentHarness:
    from .runtime import AgentHarness  # noqa: PLC0415 (import tardio evita ciclo)

    s = settings or get_settings()
    base = Path(data_dir)

    if dio:
        from ..data.dio_adapter import (  # noqa: PLC0415
            carregar_perfil_dio,
            carregar_produtos_dio,
            carregar_transacoes_dio,
        )

        transacoes = carregar_transacoes_dio(base / "transacoes.csv")
        perfil = carregar_perfil_dio(base / "perfil_investidor.json")
        produtos = carregar_produtos_dio(base / "produtos_financeiros.json")
    else:
        transacoes = carregar_transacoes(base / "transacoes.csv")
        perfil = carregar_perfil(base / "perfil_investidor.json")
        produtos = carregar_produtos(base / "produtos_financeiros.json")

    # Glossario (base de conhecimento) fica fora de data_dir; carrega se existir.
    gloss_path = Path("data/knowledge/glossario.json")
    glossario = carregar_glossario(gloss_path) if gloss_path.exists() else None

    # Amostra PIX (detector de fraude) tambem fora de data_dir; opcional.
    pix_path = Path("data/pix_sample/pix_fraud_sample.csv")
    pix_sample = pd.read_csv(pix_path) if pix_path.exists() else None

    registry = build_registry(
        transacoes, perfil, produtos, glossario=glossario, pix_sample=pix_sample, seed=s.seed
    )

    # llm injetavel: producao usa o provedor configurado; teste/demo injeta Fake.
    if llm is None:
        llm = build_llm(s)

    # Gate de suitability efetivo: a regra recebe o catalogo (id, nome) e barra
    # recomendacao de produto fora do conjunto elegivel.
    catalogo = [(p.produto_id, p.nome) for p in produtos]
    policy = PolicyGate(rules=[PromessasProibidasRule(), SuitabilityRule(catalogo)])

    return AgentHarness(
        llm,
        registry,
        system_prompt=SYSTEM_PROMPT,
        seed=s.seed,
        max_steps=s.max_agent_steps,
        abs_tol=s.number_abs_tolerance,
        rel_tol=s.number_rel_tolerance,
        regenerate_on_orphan=s.regenerate_on_orphan,
        allow_user_numbers=s.allow_numbers_from_user,
        policy=policy,
    )
