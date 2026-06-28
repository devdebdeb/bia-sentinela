"""resumo_gastos com dados injetados: numeros nascem dos dados, nao do LLM."""

from __future__ import annotations

import pandas as pd

from bia_sentinela.tools.gastos import ResumoGastosTool


def _tx() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"categoria": "renda", "valor": 5000.0},
            {"categoria": "alimentacao", "valor": -300.0},
            {"categoria": "alimentacao", "valor": -200.0},
            {"categoria": "transporte", "valor": -100.0},
        ]
    )


def test_agrega_por_categoria() -> None:
    ins = ResumoGastosTool(_tx()).run(ResumoGastosTool.input_model())
    cats = {g["categoria"]: g["total"] for g in ins.dados["gastos"]}
    assert cats["alimentacao"] == 500.0  # 300 + 200
    assert cats["transporte"] == 100.0
    assert ins.dados["total_geral"] == 600.0
    # numeros sao proveniencia: total geral + totais por categoria.
    assert 500.0 in ins.numeros and 600.0 in ins.numeros


def test_filtra_categoria() -> None:
    ins = ResumoGastosTool(_tx()).run(ResumoGastosTool.input_model(categoria="transporte"))
    assert len(ins.dados["gastos"]) == 1
    assert ins.dados["gastos"][0]["categoria"] == "transporte"


def test_sem_gastos_no_filtro() -> None:
    ins = ResumoGastosTool(_tx()).run(ResumoGastosTool.input_model(categoria="inexistente"))
    assert ins.numeros == []
