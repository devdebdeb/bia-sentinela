"""Ferramenta: detecção de anomalias em transações.

Dois detectores complementares, porque ha dois tipos de anomalia com naturezas
distintas:

- Picos pontuais (ex.: um gasto avulso de R$ 2.200 em lazer): IsolationForest
  sobre features por transacao, com um baseline estatistico (z-score robusto +
  IQR) para comparacao.
- Degraus de assinatura (ex.: streaming que pula de R$ 39,90 para R$ 89,90):
  padrao temporal por descricao que o IsolationForest, por design, nao captura
  (89,90 e um valor pequeno); detectado por `cobrancas_recorrentes` (changepoint
  por descricao recorrente).

Os valores reportados sao sempre transacoes reais do cliente — a ferramenta nao
inventa numeros, apenas pontua e ordena o que ja existe nos dados. A dependencia
scikit-learn e opcional (extra `ml`), importada de forma tardia.
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from ..data.features import cobrancas_recorrentes, features_transacao
from ..schemas import Insight

# Salto minimo (em %) para tratar um degrau de assinatura como anomalia.
_DEGRAU_MIN_PCT = 25.0


class DetectarAnomaliasInput(BaseModel):
    top_n: int = Field(default=5, ge=1, le=50, description="quantos picos pontuais retornar")


# Colunas de feature na ordem fixa que alimenta o modelo (determinismo).
_FEATURES = ["valor_abs", "z_categoria", "ratio_descricao"]


def _com_mes(df: pd.DataFrame) -> pd.DataFrame:
    """Garante a coluna 'mes' (a ingestao a cria; dados crus de teste nao)."""
    if "mes" in df.columns:
        return df
    out = df.copy()
    out["mes"] = pd.to_datetime(out["data"]).dt.to_period("M").astype(str)
    return out


def _motivo(row: pd.Series) -> str:
    """Explica em linguagem natural por que a transacao destoa."""
    if abs(row["z_categoria"]) >= 3.0:
        return f"valor atipico para a categoria '{row['categoria']}'"
    return "padrao de gasto incomum"


def pontuar_anomalias(
    transacoes: pd.DataFrame, *, seed: int = 42, contamination: float = 0.05
) -> pd.DataFrame:
    """Pontua cada saida com IsolationForest e o baseline estatistico.

    Retorna o DataFrame de features com as colunas extras `iforest_outlier`,
    `score` (maior = mais anomalo) e `baseline_outlier`. Funcao pura/
    deterministica (seed fixa): mesma entrada, mesma saida. Separada da tool
    para permitir medir recall contra rotulos sem passar pelo harness.
    """
    from sklearn.ensemble import IsolationForest  # noqa: PLC0415 (dep opcional [ml])
    from sklearn.preprocessing import StandardScaler  # noqa: PLC0415

    feats = features_transacao(transacoes)
    if feats.empty:
        return feats
    # Padroniza para os tres sinais competirem em pe de igualdade: sem isso o
    # valor_abs cru (ate milhares) abafa o ratio_descricao.
    x = StandardScaler().fit_transform(feats[_FEATURES].to_numpy())
    model = IsolationForest(n_estimators=200, contamination=contamination, random_state=seed)
    model.fit(x)
    feats = feats.assign(
        iforest_outlier=model.predict(x) == -1,
        score=(-model.decision_function(x)).round(4),
    )
    q1, q3 = feats["valor_abs"].quantile([0.25, 0.75])
    iqr = q3 - q1
    feats["baseline_outlier"] = (feats["z_categoria"].abs() >= 3.0) | (
        feats["valor_abs"] > q3 + 1.5 * iqr
    )
    return feats


def detectar_degraus(transacoes: pd.DataFrame) -> pd.DataFrame:
    """Assinaturas cujo valor deu um salto relevante (|variacao| >= limiar)."""
    rec = cobrancas_recorrentes(_com_mes(transacoes))
    if rec.empty:
        return rec
    return rec[rec["variacao_pct"].abs() >= _DEGRAU_MIN_PCT].reset_index(drop=True)


class DetectarAnomaliasTool:
    name = "detectar_anomalias"
    description = (
        "Identifica transacoes de gasto fora do padrao historico do cliente: "
        "picos avulsos atipicos e assinaturas que subiram de preco. Use quando o "
        "cliente perguntar sobre gastos estranhos, cobrancas inesperadas ou o que "
        "mudou nas contas. Retorna apenas transacoes reais, com motivo."
    )
    input_model = DetectarAnomaliasInput

    def __init__(
        self, transacoes: pd.DataFrame, *, seed: int = 42, contamination: float = 0.05
    ) -> None:
        # Dados injetados por construtor: a ferramenta nao carrega arquivo nem
        # recebe transacoes do LLM (que poderia adulterar).
        self._tx = transacoes
        self._seed = seed
        self._contamination = contamination

    def run(self, args: DetectarAnomaliasInput) -> Insight:
        feats = pontuar_anomalias(self._tx, seed=self._seed, contamination=self._contamination)
        if feats.empty:
            return Insight(
                fonte=self.name, resumo="Sem transacoes de saida para analisar.", numeros=[]
            )

        anomalias: list[dict] = []
        numeros: list[float] = []
        referencias: list[str] = []
        linhas: list[str] = []

        # 1) Picos pontuais (IsolationForest), ordenados pelo score.
        top = feats[feats["iforest_outlier"]].sort_values("score", ascending=False).head(args.top_n)
        for _, row in top.iterrows():
            valor = round(float(row["valor_abs"]), 2)
            data = str(row["data"]).split(" ")[0]
            motivo = _motivo(row)
            numeros.append(valor)
            referencias.append(f"anomalia:{row['descricao']}@{data}")
            anomalias.append(
                {
                    "tipo": "pico",
                    "data": data,
                    "descricao": str(row["descricao"]),
                    "categoria": str(row["categoria"]),
                    "valor": valor,
                    "score": float(row["score"]),
                    "motivo": motivo,
                }
            )
            linhas.append(f"R$ {valor:.2f} ({row['descricao']}, {data}): {motivo}")

        # 2) Degraus de assinatura (changepoint por descricao recorrente).
        degraus = detectar_degraus(self._tx)
        for _, row in degraus.iterrows():
            atual = round(float(row["nivel_atual"]), 2)
            inicial = round(float(row["nivel_inicial"]), 2)
            var = round(float(row["variacao_pct"]), 1)
            motivo = f"assinatura passou de R$ {inicial:.2f} para R$ {atual:.2f} ({var:+.1f}%)"
            numeros.extend([atual, inicial])
            referencias.append(f"anomalia:{row['descricao']}")
            anomalias.append(
                {
                    "tipo": "degrau_assinatura",
                    "descricao": str(row["descricao"]),
                    "nivel_inicial": inicial,
                    "nivel_atual": atual,
                    "variacao_pct": var,
                    "motivo": motivo,
                }
            )
            linhas.append(f"{row['descricao']}: {motivo}")

        n_if = int(feats["iforest_outlier"].sum())
        n_base = int(feats["baseline_outlier"].sum())
        n_overlap = int((feats["iforest_outlier"] & feats["baseline_outlier"]).sum())

        if anomalias:
            resumo = (
                f"Encontrei {len(anomalias)} anomalia(s) "
                f"({len(top)} pico(s) pontual(is), {len(degraus)} degrau(s) de assinatura). "
                + "; ".join(linhas)
                + "."
            )
        else:
            resumo = "Nenhuma transacao atipica encontrada no periodo."

        return Insight(
            fonte=self.name,
            resumo=resumo,
            numeros=numeros,
            referencias=referencias,
            dados={
                "anomalias": anomalias,
                "n_isolation_forest": n_if,
                "n_baseline_estatistico": n_base,
                "n_concordancia": n_overlap,
                "n_degraus_assinatura": int(len(degraus)),
                "contamination": self._contamination,
            },
        )
