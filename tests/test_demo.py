"""Modo demo: scan proativo e chat rodam no harness real com FakeLLM, grounded.
Nao requer Streamlit nem rede.
"""

from __future__ import annotations

import pytest

pytest.importorskip("sklearn")  # detectar_anomalias depende do extra [ml]

from bia_sentinela.demo import build_demo_harness, parse_meta, scan_proativo  # noqa: E402


def test_parse_meta_extrai_valores() -> None:
    d = parse_meta("Consigo juntar 50 mil em 5 anos guardando 700 por mes?")
    assert d["meta_valor"] == 50000.0
    assert d["meses"] == 60
    assert d["aporte_mensal"] == 700.0


def test_parse_meta_usa_defaults() -> None:
    d = parse_meta("quero simular uma meta")
    assert d["meta_valor"] == 50000.0 and d["meses"] == 60 and d["aporte_mensal"] == 700.0


def test_scan_proativo_retorna_insights_grounded() -> None:
    cards = scan_proativo()
    titulos = [t for t, _ in cards]
    assert any("fora do padrao" in t.lower() for t in titulos)
    assert any("caixa parado" in t.lower() for t in titulos)
    # Todo card carrega um Insight com resumo factual.
    for _, ins in cards:
        assert ins.resumo


def test_demo_chat_anomalia_grounded() -> None:
    res = build_demo_harness().run_turn("tenho algum gasto estranho?")
    assert not res.blocked
    assert res.verification and res.verification.ok
    assert any(t.name == "detectar_anomalias" for t in res.tool_calls)
    assert res.response.strip()


def test_demo_chat_recusa_fora_de_escopo() -> None:
    res = build_demo_harness().run_turn("me conta uma piada de futebol")
    assert "escopo" in res.response.lower()


def test_demo_chat_glossario() -> None:
    res = build_demo_harness().run_turn("o que e liquidez?")
    assert not res.blocked
    assert any(t.name == "consultar_glossario" for t in res.tool_calls)
    assert "liquidez" in res.response.lower()


def test_demo_chat_meta_grounded() -> None:
    res = build_demo_harness().run_turn("consigo juntar 50 mil em 5 anos guardando 700 por mes?")
    assert not res.blocked
    assert any(t.name == "simular_meta" for t in res.tool_calls)
    assert res.verification and res.verification.ok
