from bia_sentinela.tools.metas import SimularMetaTool


def test_simulacao_deterministica() -> None:
    tool = SimularMetaTool(seed=42)
    args = tool.input_model(meta_valor=50000, meses=60, aporte_mensal=700)
    a = tool.run(args)
    b = tool.run(args)
    assert a.dados == b.dados  # seed fixa -> resultado identico


def test_probabilidade_no_intervalo() -> None:
    tool = SimularMetaTool(seed=42)
    insight = tool.run(tool.input_model(meta_valor=50000, meses=60, aporte_mensal=700))
    prob = insight.dados["probabilidade_sucesso_pct"]
    assert 0.0 <= prob <= 100.0


def test_mais_aporte_aumenta_probabilidade() -> None:
    tool = SimularMetaTool(seed=42)
    baixo = tool.run(tool.input_model(meta_valor=60000, meses=60, aporte_mensal=500))
    alto = tool.run(tool.input_model(meta_valor=60000, meses=60, aporte_mensal=1500))
    assert (
        alto.dados["probabilidade_sucesso_pct"] > baixo.dados["probabilidade_sucesso_pct"]
    )


def test_percentis_ordenados() -> None:
    tool = SimularMetaTool(seed=42)
    insight = tool.run(tool.input_model(meta_valor=50000, meses=120, aporte_mensal=400))
    d = insight.dados
    assert d["percentil_10"] <= d["percentil_50"] <= d["percentil_90"]
    # Numeros do resumo entram na proveniencia para o verifier autorizar.
    assert set(
        [d["probabilidade_sucesso_pct"], d["valor_esperado"], d["percentil_10"]]
    ).issubset(set(insight.numeros))
