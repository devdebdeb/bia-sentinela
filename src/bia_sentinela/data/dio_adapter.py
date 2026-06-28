"""Adaptador dos dados reais do desafio DIO para os contratos internos.

Os arquivos da DIO (data/dio/) usam um schema diferente do nosso:
- transacoes: `valor` positivo + `tipo` (entrada/saida) -> convertido para o
  sinal interno (negativo = saida);
- produtos: `risco` baixo/medio/alto, `rentabilidade` em texto relativo
  ("100% da Selic"), sem id, `aporte_minimo` -> mapeados para ProdutoFinanceiro
  (risco->perfil, id gerado, rentabilidade_desc preservada);
- perfil: `perfil_investidor`, `objetivo_principal`+`metas`, `patrimonio_total`
  -> PerfilInvestidor (+ saldo_conta derivado para o caixa ocioso).

Nada e inventado: o que nao existe (ex.: liquidez, % a.a. fixo) fica None.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

from ..schemas import PerfilInvestidor, ProdutoFinanceiro, Transacao

_RISCO = {"baixo": "conservador", "medio": "moderado", "alto": "arrojado"}


def _slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto.lower())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")


def carregar_transacoes_dio(path: str | Path) -> pd.DataFrame:
    """Le transacoes da DIO e normaliza o sinal: saida vira valor negativo."""
    df = pd.read_csv(path)
    sinal = df["tipo"].str.lower().eq("entrada").map({True: 1, False: -1})
    df["valor"] = (df["valor"].abs() * sinal).astype(float)
    for rec in df.to_dict(orient="records"):
        Transacao.model_validate(rec)  # valida na fronteira
    df["data"] = pd.to_datetime(df["data"])
    df["mes"] = df["data"].dt.to_period("M").astype(str)
    return df


def _classe(categoria: str, risco_interno: str) -> str:
    if categoria == "renda_fixa":
        return "renda_fixa"
    # "fundo" e outros: separa por risco para casar com a aderencia de objetivo.
    return "renda_variavel" if risco_interno == "arrojado" else "multimercado"


def carregar_produtos_dio(path: str | Path) -> list[ProdutoFinanceiro]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    produtos: list[ProdutoFinanceiro] = []
    for p in raw:
        risco = _RISCO.get(str(p.get("risco", "")).lower(), "conservador")
        produtos.append(
            ProdutoFinanceiro(
                produto_id=_slug(p["nome"]),
                nome=p["nome"],
                classe=_classe(str(p.get("categoria", "")).lower(), risco),
                risco=risco,
                rentabilidade_aa=None,  # DIO traz rentabilidade relativa (texto)
                rentabilidade_desc=p.get("rentabilidade"),
                liquidez=None,
                aplicacao_minima=p.get("aporte_minimo"),
            )
        )
    return produtos


def _horizonte_meses(metas: list[dict], hoje: date) -> int | None:
    """Maior prazo entre as metas, em meses a partir de hoje (>=0)."""
    prazos: list[int] = []
    for m in metas:
        prazo = str(m.get("prazo", ""))
        mt = re.match(r"(\d{4})-(\d{2})", prazo)
        if mt:
            ano, mes = int(mt.group(1)), int(mt.group(2))
            prazos.append((ano - hoje.year) * 12 + (mes - hoje.month))
    return max([p for p in prazos if p >= 0], default=None) if prazos else None


def carregar_perfil_dio(path: str | Path, *, hoje: date | None = None) -> PerfilInvestidor:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    metas = raw.get("metas", [])
    objetivos = [raw["objetivo_principal"]] if raw.get("objetivo_principal") else []
    objetivos += [m["meta"] for m in metas if m.get("meta")]
    return PerfilInvestidor(
        cliente_id=_slug(raw.get("nome", "cliente_dio")) or "cliente_dio",
        perfil_risco=str(raw["perfil_investidor"]).lower(),
        renda_mensal=float(raw.get("renda_mensal", 0.0)),
        objetivos=objetivos,
        horizonte_meses=_horizonte_meses(metas, hoje or date.today()),
    )


def carregar_perfil_raw_dio(path: str | Path) -> dict:
    """Perfil cru normalizado, com saldo_conta derivado (para o caixa ocioso)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    objetivos = [raw["objetivo_principal"]] if raw.get("objetivo_principal") else []
    objetivos += [m["meta"] for m in raw.get("metas", []) if m.get("meta")]
    # saldo_conta: usamos o patrimonio total como proxy do saldo disponivel.
    raw["saldo_conta"] = float(raw.get("patrimonio_total", 0.0))
    raw["objetivos"] = objetivos
    return raw
