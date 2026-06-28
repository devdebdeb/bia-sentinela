import pandas as pd
import pytest

from bia_sentinela.data.generator import gerar_transacoes
from bia_sentinela.schemas import Insight
from bia_sentinela.tools.anomalias import (
    DetectarAnomaliasTool,
    detectar_degraus,
    pontuar_anomalias,
)

pytest.importorskip("sklearn")  # ferramenta depende do extra [ml]


@pytest.fixture(scope="module")
def df_rotulado() -> pd.DataFrame:
    # Mantem o rotulo is_anomaly para medir recall.
    tx, _ = gerar_transacoes(seed=42)
    return tx


def test_pontuacao_deterministica(df_rotulado: pd.DataFrame) -> None:
    a = pontuar_anomalias(df_rotulado, seed=42)
    b = pontuar_anomalias(df_rotulado, seed=42)
    assert a["score"].tolist() == b["score"].tolist()


def test_recall_contra_rotulos(df_rotulado: pd.DataFrame) -> None:
    # Cobertura combinada: uma anomalia plantada conta como detectada se o
    # IsolationForest a marca (pico pontual) OU se sua descricao aparece como
    # degrau de assinatura (sinal temporal que o IF nao captura por design).
    feats = pontuar_anomalias(df_rotulado, seed=42)
    descricoes_degrau = set(detectar_degraus(df_rotulado)["descricao"])

    rotulo = df_rotulado.loc[feats.index, "is_anomaly"]
    coberta = feats["iforest_outlier"] | feats["descricao"].isin(descricoes_degrau)
    plantadas = int(rotulo.sum())
    acertos = int((rotulo & coberta).sum())
    recall = acertos / plantadas
    assert recall >= 0.8, f"recall={recall:.2f} ({acertos}/{plantadas})"


def test_tool_retorna_anomalias_principais(df_rotulado: pd.DataFrame) -> None:
    tool = DetectarAnomaliasTool(df_rotulado, seed=42)
    insight = tool.run(tool.input_model(top_n=10))
    assert isinstance(insight, Insight)
    descricoes = " ".join(a["descricao"] for a in insight.dados["anomalias"])
    # O pico de lazer (-2200) e o salto de assinatura sao os sinais mais fortes.
    assert "Lazer - compra atipica" in descricoes
    assert "Streaming" in descricoes
    # Todo numero do resumo precisa estar na proveniencia (contrato do verifier).
    assert insight.numeros


def test_sem_saidas_retorna_insight_vazio() -> None:
    so_entradas = pd.DataFrame(
        [{"data": "2025-01-05", "descricao": "Salario", "categoria": "renda", "valor": 9000.0}]
    )
    tool = DetectarAnomaliasTool(so_entradas, seed=42)
    insight = tool.run(tool.input_model())
    assert insight.numeros == []
