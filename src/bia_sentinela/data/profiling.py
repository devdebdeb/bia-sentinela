"""Relatório de qualidade dos dados (cobertura, nulos, faixas de valor)."""

from __future__ import annotations

import pandas as pd


def perfil_qualidade(df: pd.DataFrame) -> dict:
    n = len(df)
    nulos = {c: int(df[c].isna().sum()) for c in df.columns}
    return {
        "n_registros": n,
        "periodo": {
            "inicio": str(df["data"].min().date()),
            "fim": str(df["data"].max().date()),
            "meses_distintos": int(df["mes"].nunique()),
        },
        "nulos_por_coluna": nulos,
        "pct_nulos_valor": round(nulos.get("valor", 0) / n * 100, 2) if n else 0.0,
        "categorias_distintas": int(df["categoria"].nunique()),
        "valor": {
            "min": round(float(df["valor"].min()), 2),
            "max": round(float(df["valor"].max()), 2),
            "media_saidas": round(float(df.loc[df["valor"] < 0, "valor"].mean()), 2),
        },
    }
