from bia_sentinela.guardrails.verifier import NumericVerifier, _normalize
from bia_sentinela.schemas import Insight


def test_grounded_passes() -> None:
    ins = [Insight(fonte="t", resumo="ok", numeros=[162.55])]
    rep = NumericVerifier().check("Você gastou R$ 162.55 no mês.", ins)
    assert rep.ok and not rep.orphans


def test_orphan_blocked() -> None:
    ins = [Insight(fonte="t", resumo="ok", numeros=[162.55])]
    rep = NumericVerifier().check("Você gastou R$ 999,99 no mês.", ins)
    assert not rep.ok and rep.orphans


def test_user_number_allowed() -> None:
    rep = NumericVerifier().check("Você quer juntar R$ 5000.", [], user_numbers=[5000.0])
    assert rep.ok


def test_normalize_br_format() -> None:
    assert _normalize("R$ 1.234,56") == 1234.56
    assert _normalize("12,5%") == 12.5
    assert _normalize("1.000") == 1000.0
