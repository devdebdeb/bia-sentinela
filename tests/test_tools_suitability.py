import pytest

from bia_sentinela.data.generator import gerar_perfil, gerar_produtos
from bia_sentinela.schemas import PerfilInvestidor, ProdutoFinanceiro
from bia_sentinela.tools.suitability import SuitabilidadeTool


@pytest.fixture
def produtos() -> list[ProdutoFinanceiro]:
    return [ProdutoFinanceiro.model_validate(p) for p in gerar_produtos()]


@pytest.fixture
def perfil() -> PerfilInvestidor:
    return PerfilInvestidor.model_validate(gerar_perfil())


def test_bloqueia_risco_acima_do_perfil(
    perfil: PerfilInvestidor, produtos: list[ProdutoFinanceiro]
) -> None:
    tool = SuitabilidadeTool(perfil, produtos)  # perfil moderado
    insight = tool.run(tool.input_model())
    bloqueados = {b["produto_id"] for b in insight.dados["bloqueados"]}
    # Produtos arrojados ficam fora do teto de um perfil moderado.
    assert "p_acoes" in bloqueados
    assert "p_cripto" in bloqueados
    assert "p_acoes" not in insight.referencias


def test_elegiveis_sao_o_teto(
    perfil: PerfilInvestidor, produtos: list[ProdutoFinanceiro]
) -> None:
    tool = SuitabilidadeTool(perfil, produtos)
    insight = tool.run(tool.input_model())
    # referencias = ids elegiveis, consumidos pela politica de suitability.
    assert insight.referencias
    assert all(pid.startswith("p_") for pid in insight.referencias)


def test_ranqueia_renda_fixa_para_reserva(
    perfil: PerfilInvestidor, produtos: list[ProdutoFinanceiro]
) -> None:
    tool = SuitabilidadeTool(perfil, produtos)
    insight = tool.run(tool.input_model(objetivo="reserva de emergencia"))
    top = insight.dados["elegiveis"][0]
    assert top["classe"] == "renda_fixa"  # mais aderente a reserva


def test_filtra_por_valor_disponivel(
    perfil: PerfilInvestidor, produtos: list[ProdutoFinanceiro]
) -> None:
    tool = SuitabilidadeTool(perfil, produtos)
    insight = tool.run(tool.input_model(valor_disponivel=100.0))
    # CDB Prefixado e Multimercado exigem R$ 500; ficam bloqueados.
    bloqueados = {b["produto_id"] for b in insight.dados["bloqueados"]}
    assert "p_cdb_pre" in bloqueados
