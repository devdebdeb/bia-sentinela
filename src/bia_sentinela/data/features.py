"""Feature engineering sobre as transações.

Features determinísticas que alimentam a análise e o detector de anomalias.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fluxo_mensal(df: pd.DataFrame) -> pd.DataFrame:
    """Entradas, saídas e poupança por mês."""
    g = df.groupby("mes").agg(
        entradas=("valor", lambda s: s[s > 0].sum()),
        saidas=("valor", lambda s: -s[s < 0].sum()),
    )
    g["poupanca"] = g["entradas"] - g["saidas"]
    g["taxa_poupanca"] = (g["poupanca"] / g["entradas"]).replace([np.inf, -np.inf], 0).fillna(0)
    return g.reset_index()


def gasto_por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    saidas = df[df["valor"] < 0].copy()
    g = saidas.groupby("categoria")["valor"].sum().abs().sort_values(ascending=False)
    out = g.reset_index().rename(columns={"valor": "total"})
    out["share"] = (out["total"] / out["total"].sum()).round(4)
    return out


def media_movel_gastos(df: pd.DataFrame, janela: int = 3) -> pd.DataFrame:
    fm = fluxo_mensal(df)
    fm["saidas_mm"] = fm["saidas"].rolling(janela, min_periods=1).mean().round(2)
    fm["desvio_vs_mm"] = ((fm["saidas"] - fm["saidas_mm"]) / fm["saidas_mm"]).round(3)
    return fm


def _melhor_changepoint(vals: pd.Series, cov_max: float) -> tuple[int | None, float, float]:
    """Acha o ponto de quebra que separa dois patamares estáveis.

    Retorna (índice_do_split, nível_antes, nível_depois). Se não houver quebra
    limpa, o split é None e os níveis são a média global.
    """
    best_k, best_cost = None, float("inf")
    for k in range(2, len(vals) - 1):
        left, right = vals.iloc[:k], vals.iloc[k:]
        cov_l = left.std(ddof=0) / left.mean() if left.mean() else 1.0
        cov_r = right.std(ddof=0) / right.mean() if right.mean() else 1.0
        cost = max(cov_l, cov_r)
        if cost < best_cost:
            best_k, best_cost = k, cost
    if best_k is not None and best_cost <= cov_max:
        return best_k, round(vals.iloc[:best_k].mean(), 2), round(vals.iloc[best_k:].mean(), 2)
    media = round(vals.mean(), 2)
    return None, media, media


def cobrancas_recorrentes(
    df: pd.DataFrame, cov_max: float = 0.10, max_por_mes: float = 1.5
) -> pd.DataFrame:
    """Detecta assinaturas (linha única recorrente) e seu degrau de preço.

    Critérios para ser assinatura: aparece em >=4 meses e tem ~1 cobrança por
    mês (linha única, não compras avulsas). O degrau é achado por changepoint
    entre dois patamares estáveis.
    """
    saidas = df[df["valor"] < 0].copy()
    linhas: list[dict] = []
    for desc, grupo in saidas.groupby("descricao"):
        por_mes = grupo.groupby("mes")["valor"].agg(["sum", "count"])
        if len(por_mes) < 4 or por_mes["count"].mean() > max_por_mes:
            continue
        vals = por_mes["sum"].abs().sort_index()
        k, n1, n2 = _melhor_changepoint(vals, cov_max)
        if k is None and (vals.std(ddof=0) / vals.mean() if vals.mean() else 1.0) > cov_max:
            continue  # nem estável nem com degrau limpo -> não é assinatura
        ratio = round(n2 / n1, 3) if n1 else 1.0
        linhas.append(
            {
                "descricao": desc,
                "meses": int(len(vals)),
                "nivel_inicial": n1,
                "nivel_atual": n2,
                "variacao_pct": round((ratio - 1) * 100, 1),
            }
        )
    out = pd.DataFrame(linhas)
    if out.empty:
        return out
    ordem = out["variacao_pct"].abs().sort_values(ascending=False).index
    return out.reindex(ordem).reset_index(drop=True)


def _z_robusto(s: pd.Series) -> pd.Series:
    """Z-score robusto (mediana/MAD) — resiste a outliers melhor que media/desvio."""
    med = s.median()
    mad = (s - med).abs().median()
    escala = mad * 1.4826  # MAD -> desvio-padrão equivalente sob normalidade
    if escala == 0:
        return pd.Series(0.0, index=s.index)
    return (s - med) / escala


def features_transacao(df: pd.DataFrame) -> pd.DataFrame:
    """Features por transacao de saida, base do detector de anomalias.

    Cada saida (valor < 0) vira uma linha com:
    - valor_abs: magnitude do gasto.
    - z_categoria: desvio robusto do valor dentro da propria categoria (um gasto
      de R$ 2.200 em lazer destoa do padrao da categoria).
    - ratio_descricao: valor sobre a mediana da mesma descricao recorrente
      (>=3 ocorrencias); captura degraus de assinatura (39,90 -> 89,90 = 2.25).
      Vale 1.0 quando a descricao nao e recorrente, para nao gerar falso sinal.
    """
    saidas = df[df["valor"] < 0].copy()
    if saidas.empty:
        return saidas.assign(valor_abs=[], z_categoria=[], ratio_descricao=[])
    saidas["valor_abs"] = saidas["valor"].abs()
    saidas["z_categoria"] = saidas.groupby("categoria")["valor_abs"].transform(_z_robusto)

    med_desc = saidas.groupby("descricao")["valor_abs"].transform("median")
    cnt_desc = saidas.groupby("descricao")["valor_abs"].transform("count")
    ratio = saidas["valor_abs"] / med_desc.replace(0, np.nan)
    saidas["ratio_descricao"] = ratio.where(cnt_desc >= 3, 1.0).fillna(1.0)
    return saidas


def caixa_ocioso(saldo_conta: float, fluxo: pd.DataFrame, meses_reserva: int = 6) -> dict:
    """Quanto há em caixa acima de uma reserva de emergência saudável."""
    gasto_medio = float(fluxo["saidas"].mean())
    reserva_recomendada = round(gasto_medio * meses_reserva, 2)
    ocioso = round(max(0.0, saldo_conta - reserva_recomendada), 2)
    return {
        "saldo_conta": saldo_conta,
        "gasto_medio_mensal": round(gasto_medio, 2),
        "reserva_recomendada": reserva_recomendada,
        "caixa_ocioso": ocioso,
    }
