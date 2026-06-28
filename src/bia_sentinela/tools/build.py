"""Montagem do ToolRegistry com as ferramentas reais.

Centraliza a injecao de dependencia: os dados (transacoes, perfil, catalogo,
glossario) sao carregados uma vez e injetados nas ferramentas por construtor.
As fabricas de harness (offline e producao) consomem este registry.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..data.ingestion import (
    carregar_glossario,
    carregar_perfil,
    carregar_produtos,
    carregar_transacoes,
)
from ..schemas import PerfilInvestidor, ProdutoFinanceiro
from .anomalias import DetectarAnomaliasTool
from .base import ToolRegistry
from .conhecimento import ConsultarGlossarioTool, ConsultarProdutoTool
from .fraude import build_fraude_tool
from .gastos import ResumoGastosTool
from .metas import SimularMetaTool
from .suitability import SuitabilidadeTool


def build_registry(
    transacoes: pd.DataFrame,
    perfil: PerfilInvestidor,
    produtos: list[ProdutoFinanceiro],
    *,
    glossario: dict[str, str] | None = None,
    pix_sample: pd.DataFrame | None = None,
    seed: int = 42,
) -> ToolRegistry:
    """Registra as ferramentas reais com os dados ja carregados injetados."""
    registry = ToolRegistry()
    registry.register(ResumoGastosTool(transacoes))  # dados injetados, nao via LLM
    registry.register(DetectarAnomaliasTool(transacoes, seed=seed))
    registry.register(SuitabilidadeTool(perfil, produtos))
    registry.register(SimularMetaTool(seed=seed))
    registry.register(ConsultarProdutoTool(produtos))
    if glossario:
        registry.register(ConsultarGlossarioTool(glossario))
    if pix_sample is not None and not pix_sample.empty:
        fraude_tool, _metricas = build_fraude_tool(pix_sample, seed=seed)
        registry.register(fraude_tool)
    return registry


def _glossario_e_pix(
    glossario_path: str | Path, pix_sample_path: str | Path
) -> tuple[dict[str, str] | None, pd.DataFrame | None]:
    gloss_path = Path(glossario_path)
    glossario = carregar_glossario(gloss_path) if gloss_path.exists() else None
    pix_path = Path(pix_sample_path)
    pix_sample = pd.read_csv(pix_path) if pix_path.exists() else None
    return glossario, pix_sample


def build_registry_from_disk(
    data_dir: str | Path = "data/raw",
    *,
    glossario_path: str | Path = "data/knowledge/glossario.json",
    pix_sample_path: str | Path = "data/pix_sample/pix_fraud_sample.csv",
    seed: int = 42,
) -> ToolRegistry:
    """Carrega os dados sinteticos (formato interno) e monta o registry."""
    base = Path(data_dir)
    transacoes = carregar_transacoes(base / "transacoes.csv")
    perfil = carregar_perfil(base / "perfil_investidor.json")
    produtos = carregar_produtos(base / "produtos_financeiros.json")
    glossario, pix_sample = _glossario_e_pix(glossario_path, pix_sample_path)
    return build_registry(
        transacoes, perfil, produtos, glossario=glossario, pix_sample=pix_sample, seed=seed
    )


def build_registry_dio(
    data_dir: str | Path = "data/dio",
    *,
    glossario_path: str | Path = "data/knowledge/glossario.json",
    pix_sample_path: str | Path = "data/pix_sample/pix_fraud_sample.csv",
    seed: int = 42,
) -> ToolRegistry:
    """Carrega os dados REAIS da DIO (via adaptador) e monta o registry.

    O glossario e a amostra PIX (conhecimento/fraude) sao compartilhados, nao
    dependem do formato dos dados do cliente.
    """
    from ..data.dio_adapter import (  # noqa: PLC0415
        carregar_perfil_dio,
        carregar_produtos_dio,
        carregar_transacoes_dio,
    )

    base = Path(data_dir)
    transacoes = carregar_transacoes_dio(base / "transacoes.csv")
    perfil = carregar_perfil_dio(base / "perfil_investidor.json")
    produtos = carregar_produtos_dio(base / "produtos_financeiros.json")
    glossario, pix_sample = _glossario_e_pix(glossario_path, pix_sample_path)
    return build_registry(
        transacoes, perfil, produtos, glossario=glossario, pix_sample=pix_sample, seed=seed
    )
