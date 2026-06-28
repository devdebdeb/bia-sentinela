"""Detector de golpe PIX: treino deterministico, metricas no holdout e scoring.
Usa a amostra comitada (data/pix_sample). Pulado sem sklearn ou sem a amostra.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("sklearn")

_SAMPLE = Path("data/pix_sample/pix_fraud_sample.csv")
pytestmark = pytest.mark.skipif(not _SAMPLE.exists(), reason="amostra pix nao presente")

from bia_sentinela.tools.fraude import (  # noqa: E402
    build_fraude_tool,
    treinar_modelo,
)


@pytest.fixture(scope="module")
def amostra() -> pd.DataFrame:
    return pd.read_csv(_SAMPLE)


def test_treino_deterministico(amostra: pd.DataFrame) -> None:
    m1 = treinar_modelo(amostra, seed=42)
    m2 = treinar_modelo(amostra, seed=42)
    p1 = m1.predict_proba(amostra[m1.feature_names_in_])[:, 1]
    p2 = m2.predict_proba(amostra[m2.feature_names_in_])[:, 1]
    assert (p1 == p2).all()


def test_metricas_holdout_razoaveis(amostra: pd.DataFrame) -> None:
    _, met = build_fraude_tool(amostra, seed=42)
    # Os sinais de drenagem de saldo sao fortes; o modelo deve separar bem.
    assert met["roc_auc"] >= 0.85, met
    assert met["n_fraude_test"] > 0


def test_tool_sinaliza_e_e_grounded(amostra: pd.DataFrame) -> None:
    tool, _ = build_fraude_tool(amostra, seed=42)
    ins = tool.run(tool.input_model(top_n=5))
    # O conjunto de monitoramento inclui golpes -> deve haver alerta com numeros.
    assert ins.dados["alertas"]
    assert ins.numeros
    assert ins.referencias == ["modelo:pix-fraud-br"]
