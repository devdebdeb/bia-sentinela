"""Ferramenta: detecção de golpe de PIX (supervisionada).

Complementa o `detectar_anomalias` (nao-supervisionado, sobre o gasto pessoal):
aqui o problema e fraude cross-conta (golpe de engenharia social -> conta
laranja), aprendido com rotulos. Modelo sklearn treinado numa amostra
estratificada do dataset `andremessina/pix-fraud-br` (sintetico, derivado do
PaySim, ODC-BY) — ver data/pix_sample/README.md.

A tool monitora um conjunto de transferencias PIX do cliente (injetado por
construtor) e sinaliza as de alto risco, com a probabilidade e os motivos. Os
numeros nascem aqui (modelo + dados), nunca no LLM. Treino e inferencia sao
deterministicos (seed fixa).
"""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from ..schemas import Insight

# Colunas booleanas (viram int) e categorica; o resto e numerico.
_BOOL = ["dia_util", "horario_noturno", "acima_limite_noturno"]
_CAT = ["tipo_transacao"]
_NUM = [
    "valor_brl",
    "saldo_anterior_pagador",
    "saldo_posterior_pagador",
    "saldo_anterior_recebedor",
    "saldo_posterior_recebedor",
    "hora_dia",
    "razao_saldo_residual",
    "proporcao_valor_recebedor",
]
ALVO = "fraude"


def _preparar(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in _BOOL:
        if c in out.columns:
            out[c] = out[c].astype(int)
    return out


def treinar_modelo(df_train: pd.DataFrame, *, seed: int = 42):  # noqa: ANN201
    """Treina o classificador de fraude. Determinístico (random_state=seed)."""
    from sklearn.compose import ColumnTransformer  # noqa: PLC0415
    from sklearn.ensemble import RandomForestClassifier  # noqa: PLC0415
    from sklearn.pipeline import Pipeline  # noqa: PLC0415
    from sklearn.preprocessing import OneHotEncoder  # noqa: PLC0415

    pre = ColumnTransformer(
        [("cat", OneHotEncoder(handle_unknown="ignore"), _CAT)],
        remainder="passthrough",
    )
    modelo = Pipeline(
        [
            ("pre", pre),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=12,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=1,  # n_jobs=1 mantem reprodutibilidade exata
                ),
            ),
        ]
    )
    feat = _preparar(df_train)
    modelo.fit(feat[_BOOL + _NUM + _CAT], feat[ALVO])
    return modelo


def avaliar_holdout(modelo, df_test: pd.DataFrame) -> dict[str, float]:  # noqa: ANN001
    """Metricas honestas num holdout estratificado (ROC-AUC, PR-AUC, recall)."""
    from sklearn.metrics import (  # noqa: PLC0415
        average_precision_score,
        precision_score,
        recall_score,
        roc_auc_score,
    )

    feat = _preparar(df_test)
    x = feat[_BOOL + _NUM + _CAT]
    proba = modelo.predict_proba(x)[:, 1]
    pred = (proba >= 0.5).astype(int)
    y = feat[ALVO]
    return {
        "roc_auc": round(float(roc_auc_score(y, proba)), 4),
        "pr_auc": round(float(average_precision_score(y, proba)), 4),
        "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
        "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
        "n_test": int(len(y)),
        "n_fraude_test": int(y.sum()),
    }


def _motivos(row: pd.Series) -> list[str]:
    """Sinais legiveis de golpe, derivados das features da transacao."""
    m: list[str] = []
    if row.get("razao_saldo_residual", 1.0) <= 0.1:
        m.append("conta do pagador foi praticamente esvaziada")
    if row.get("horario_noturno", False) and row.get("acima_limite_noturno", False):
        m.append("valor alto em horario noturno")
    if row.get("proporcao_valor_recebedor", 0.0) >= 0.9:
        m.append("valor concentra quase todo o movimento da conta destino")
    if row.get("saldo_anterior_recebedor", 1.0) < 1000:
        m.append("conta destino com saldo historico muito baixo (possivel laranja)")
    return m or ["padrao compativel com fraude segundo o modelo"]


def build_fraude_tool(
    amostra: pd.DataFrame, *, seed: int = 42
) -> tuple[DetectarFraudePixTool, dict[str, float]]:
    """Treina o modelo na amostra e monta a tool com um conjunto a monitorar.

    Split estratificado: treina no train, mede no holdout, e usa uma fatia do
    holdout (nao vista no treino) como as transferencias PIX do cliente a
    monitorar. Retorna (tool, metricas_holdout).
    """
    from sklearn.model_selection import train_test_split  # noqa: PLC0415

    train, test = train_test_split(
        amostra, test_size=0.25, stratify=amostra[ALVO], random_state=seed
    )
    modelo = treinar_modelo(train, seed=seed)
    metricas = avaliar_holdout(modelo, test)

    # Conjunto de monitoramento: alguns golpes + legitimas do holdout, fixo.
    fraude = test[test[ALVO] == 1].head(4)
    legit = test[test[ALVO] == 0].head(8)
    monitor = pd.concat([fraude, legit]).sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return DetectarFraudePixTool(modelo, monitor), metricas


class DetectarFraudePixInput(BaseModel):
    top_n: int = Field(default=5, ge=1, le=50, description="quantos alertas retornar")
    limiar: float = Field(default=0.5, ge=0.0, le=1.0, description="probabilidade minima")


class DetectarFraudePixTool:
    name = "detectar_fraude_pix"
    description = (
        "Avalia as transferencias PIX recentes do cliente e sinaliza as de alto "
        "risco de golpe (engenharia social / conta laranja), com probabilidade e "
        "motivos. Use para 'caiu algum golpe', 'esse PIX e seguro', 'fui vitima de "
        "fraude'. Modelo supervisionado; nao inventa valores."
    )
    input_model = DetectarFraudePixInput

    def __init__(self, modelo, transacoes_pix: pd.DataFrame) -> None:  # noqa: ANN001
        # Modelo treinado e o conjunto de PIX do cliente a monitorar, injetados.
        self._modelo = modelo
        self._tx = transacoes_pix

    def run(self, args: DetectarFraudePixInput) -> Insight:
        if self._tx.empty:
            return Insight(
                fonte=self.name, resumo="Sem transferencias PIX para avaliar.", numeros=[]
            )
        feat = _preparar(self._tx)
        proba = self._modelo.predict_proba(feat[_BOOL + _NUM + _CAT])[:, 1]
        scored = self._tx.assign(prob_fraude=proba).sort_values("prob_fraude", ascending=False)
        flag = scored[scored["prob_fraude"] >= args.limiar].head(args.top_n)

        alertas: list[dict[str, Any]] = []
        numeros: list[float] = []
        linhas: list[str] = []
        for _, row in flag.iterrows():
            pct = round(float(row["prob_fraude"]) * 100, 1)
            valor = round(float(row["valor_brl"]), 2)
            motivos = _motivos(row)
            numeros.extend([pct, valor])
            alertas.append(
                {
                    "valor": valor,
                    "tipo_transacao": str(row["tipo_transacao"]),
                    "prob_fraude_pct": pct,
                    "motivos": motivos,
                }
            )
            linhas.append(
                f"R$ {valor:.2f} ({row['tipo_transacao']}): {pct:.1f}% de risco — "
                + "; ".join(motivos)
            )

        if alertas:
            resumo = (
                f"Encontrei {len(alertas)} transferencia(s) PIX com alto risco de golpe. "
                + " | ".join(linhas)
                + "."
            )
        else:
            resumo = "Nenhuma transferencia PIX recente com risco relevante de golpe."

        return Insight(
            fonte=self.name,
            resumo=resumo,
            numeros=numeros,
            referencias=["modelo:pix-fraud-br"],
            dados={"alertas": alertas, "n_avaliadas": int(len(self._tx)), "limiar": args.limiar},
        )
