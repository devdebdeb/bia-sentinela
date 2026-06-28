import pytest

from bia_sentinela.data.generator import gerar_produtos
from bia_sentinela.schemas import ProdutoFinanceiro
from bia_sentinela.tools.conhecimento import ConsultarGlossarioTool, ConsultarProdutoTool

_GLOSSARIO = {
    "CDB": "Certificado de Deposito Bancario: titulo de renda fixa emitido por bancos.",
    "liquidez": "Facilidade de transformar um investimento em dinheiro.",
}


@pytest.fixture
def produtos() -> list[ProdutoFinanceiro]:
    return [ProdutoFinanceiro.model_validate(p) for p in gerar_produtos()]


def test_glossario_define_termo() -> None:
    tool = ConsultarGlossarioTool(_GLOSSARIO)
    ins = tool.run(tool.input_model(termo="CDB"))
    assert ins.dados["encontrado"]
    assert "renda fixa" in ins.resumo


def test_glossario_ignora_acentos_e_caixa() -> None:
    tool = ConsultarGlossarioTool({"liquidez diaria": "resgate no mesmo dia util."})
    ins = tool.run(tool.input_model(termo="Liquidez Diária"))
    assert ins.dados["encontrado"]


def test_glossario_termo_ausente() -> None:
    tool = ConsultarGlossarioTool(_GLOSSARIO)
    ins = tool.run(tool.input_model(termo="blockchain quantico"))
    assert not ins.dados["encontrado"]
    assert ins.numeros == []


def test_produto_por_id_traz_numeros(produtos: list[ProdutoFinanceiro]) -> None:
    tool = ConsultarProdutoTool(produtos)
    ins = tool.run(tool.input_model(consulta="p_cdb_liq"))
    assert ins.dados["encontrado"]
    assert ins.referencias == ["p_cdb_liq"]
    # rentabilidade e aplicacao minima entram como proveniencia.
    assert ins.numeros


def test_produto_por_nome_parcial(produtos: list[ProdutoFinanceiro]) -> None:
    tool = ConsultarProdutoTool(produtos)
    ins = tool.run(tool.input_model(consulta="Tesouro Selic"))
    assert ins.dados["encontrado"]
    assert ins.dados["produto_id"] == "p_tesouro_selic"


def test_produto_ausente(produtos: list[ProdutoFinanceiro]) -> None:
    tool = ConsultarProdutoTool(produtos)
    ins = tool.run(tool.input_model(consulta="cofrinho magico"))
    assert not ins.dados["encontrado"]
