import pandas as pd
import pytest

from bia_sentinela.data import features as F
from bia_sentinela.data.generator import gerar_transacoes
from bia_sentinela.data.profiling import perfil_qualidade


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    tx, _ = gerar_transacoes(seed=42)
    tx = tx.drop(columns=["is_anomaly"])
    tx["data"] = pd.to_datetime(tx["data"])
    tx["mes"] = tx["data"].dt.to_period("M").astype(str)
    return tx


def test_geracao_deterministica() -> None:
    a, _ = gerar_transacoes(seed=42)
    b, _ = gerar_transacoes(seed=42)
    assert a.equals(b)  # mesma seed -> mesmos dados (reprodutibilidade)


def test_qualidade_sem_nulos_em_valor(df: pd.DataFrame) -> None:
    q = perfil_qualidade(df)
    assert q["pct_nulos_valor"] == 0.0
    assert q["periodo"]["meses_distintos"] == 12


def test_detecta_assinatura_que_dobrou(df: pd.DataFrame) -> None:
    rec = F.cobrancas_recorrentes(df)
    top = rec.iloc[0]
    assert "Streaming" in top["descricao"]
    assert top["variacao_pct"] > 100  # ~+125%


def test_caixa_ocioso_positivo(df: pd.DataFrame) -> None:
    fm = F.fluxo_mensal(df)
    co = F.caixa_ocioso(38000.0, fm)
    assert co["caixa_ocioso"] > 0
    assert co["reserva_recomendada"] > 0
