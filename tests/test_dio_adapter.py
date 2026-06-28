"""Adaptador dos dados reais da DIO -> contratos internos, e integracao."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from bia_sentinela.data.dio_adapter import (
    carregar_perfil_dio,
    carregar_produtos_dio,
    carregar_transacoes_dio,
)
from bia_sentinela.schemas import PerfilRisco

_DIO = Path("data/dio")
pytestmark = pytest.mark.skipif(not _DIO.exists(), reason="dados DIO nao presentes")


def test_transacoes_sinal_normalizado() -> None:
    df = carregar_transacoes_dio(_DIO / "transacoes.csv")
    # Salario (entrada) fica positivo; gastos (saida) ficam negativos.
    assert (df["valor"] > 0).sum() == 1
    assert (df["valor"] < 0).sum() == len(df) - 1
    assert "mes" in df.columns


def test_perfil_mapeado() -> None:
    p = carregar_perfil_dio(_DIO / "perfil_investidor.json", hoje=date(2026, 6, 28))
    assert p.perfil_risco == PerfilRisco.moderado
    assert p.horizonte_meses == 18  # meta mais distante (2027-12)
    assert any("reserva" in o.lower() for o in p.objetivos)


def test_produtos_mapeados() -> None:
    prods = {p.produto_id: p for p in carregar_produtos_dio(_DIO / "produtos_financeiros.json")}
    assert prods["tesouro_selic"].risco == PerfilRisco.conservador
    assert prods["fundo_de_acoes"].risco == PerfilRisco.arrojado
    # Rentabilidade relativa (texto) preservada; sem % a.a. fixo inventado.
    assert prods["tesouro_selic"].rentabilidade_aa is None
    assert prods["tesouro_selic"].rentabilidade_desc == "100% da Selic"
    assert prods["fundo_de_acoes"].classe == "renda_variavel"


@pytest.mark.skipif(not (_DIO / "transacoes.csv").exists(), reason="dados DIO")
def test_demo_dio_suitability_grounded() -> None:
    pytest.importorskip("sklearn")
    from bia_sentinela.demo import build_demo_harness

    res = build_demo_harness(dio=True).run_turn("onde invisto pensando em reserva de emergencia?")
    assert not res.blocked
    assert any(c.name == "avaliar_suitability" for c in res.tool_calls)
    # Perfil moderado: Fundo de Acoes (arrojado) nao deve ser elegivel.
    assert res.verification and res.verification.ok


def test_scan_proativo_dio() -> None:
    pytest.importorskip("sklearn")
    from bia_sentinela.demo import scan_proativo

    cards = scan_proativo(dio=True)
    assert any("produtos adequados" in t.lower() for t, _ in cards)
