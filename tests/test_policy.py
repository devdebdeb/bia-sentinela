from bia_sentinela.guardrails.policy import (
    PolicyGate,
    PromessasProibidasRule,
    SuitabilityRule,
)


def test_blocks_guaranteed_return() -> None:
    rep = PolicyGate().check("Este investimento tem rentabilidade garantida.")
    assert not rep.ok and rep.violations[0].rule == "promessas_proibidas"


def test_allows_normal_text() -> None:
    rep = PolicyGate().check("Esse CDB tem rendimento atrelado ao CDI, com risco baixo.")
    assert rep.ok


_CATALOGO = [("p_cdb_liq", "CDB Liquidez Diaria"), ("p_cripto", "Fundo Cripto")]


def test_suitability_inerte_sem_catalogo() -> None:
    # Sem catalogo injetado, a regra preserva o comportamento offline (no-op).
    rule = SuitabilityRule()
    assert rule.evaluate("Sugiro o Fundo Cripto.", allowed_products=[]) is None


def test_suitability_bloqueia_produto_fora_do_elegivel() -> None:
    gate = PolicyGate(rules=[PromessasProibidasRule(), SuitabilityRule(_CATALOGO)])
    rep = gate.check("Recomendo o Fundo Cripto para voce.", allowed_products=["p_cdb_liq"])
    assert not rep.ok and rep.violations[0].rule == "suitability"


def test_suitability_permite_produto_elegivel() -> None:
    gate = PolicyGate(rules=[PromessasProibidasRule(), SuitabilityRule(_CATALOGO)])
    rep = gate.check("O CDB Liquidez Diaria atende seu objetivo.", allowed_products=["p_cdb_liq"])
    assert rep.ok
