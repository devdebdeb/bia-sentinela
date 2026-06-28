"""Ingestão de dados.

Carrega os arquivos do desafio e valida cada registro contra os contratos de
`schemas.py`. Retorna DataFrames limpos prontos para a análise.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..schemas import PerfilInvestidor, ProdutoFinanceiro, Transacao


def carregar_transacoes(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Validação registro a registro (amostra de robustez; em volume, use Pandera).
    for rec in df.to_dict(orient="records"):
        Transacao.model_validate(rec)
    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    return df


def carregar_perfil(path: str | Path) -> PerfilInvestidor:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    # saldo_conta é extra ao contrato base; lido via carregar_perfil_raw.
    return PerfilInvestidor.model_validate(raw)


def carregar_perfil_raw(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def carregar_produtos(path: str | Path) -> list[ProdutoFinanceiro]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ProdutoFinanceiro.model_validate(p) for p in raw]


def carregar_glossario(path: str | Path) -> dict[str, str]:
    """Glossario estatico (termo -> definicao); base de conhecimento inerte."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
