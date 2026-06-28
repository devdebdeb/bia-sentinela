"""Ferramenta: adequacao (suitability) de produtos ao perfil.

Filtra o catalogo pelo perfil de risco do cliente (regra `perfil_atende` de
schemas) e pela aplicacao minima, depois ranqueia os elegiveis por aderencia ao
objetivo e ao horizonte. O conjunto elegivel e o TETO do que o agente pode
recomendar — produtos bloqueados saem com a justificativa do bloqueio.

Perfil e catalogo entram por construtor (injecao de dependencia); o LLM so
informa objetivo e valor disponivel.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..schemas import Insight, PerfilInvestidor, ProdutoFinanceiro, perfil_atende

# Aderencia de cada classe de produto a um objetivo, em [0,1]. Heuristica
# deterministica e explicavel; nao e recomendacao por si — apenas ordena os ja
# elegiveis. Chave: objetivo normalizado.
_ADERENCIA_OBJETIVO: dict[str, dict[str, float]] = {
    "reserva de emergencia": {"renda_fixa": 1.0, "multimercado": 0.4, "renda_variavel": 0.1},
    "aposentadoria": {"renda_fixa": 0.6, "multimercado": 0.9, "renda_variavel": 1.0},
    "viagem": {"renda_fixa": 1.0, "multimercado": 0.5, "renda_variavel": 0.2},
    "compra de imovel": {"renda_fixa": 0.9, "multimercado": 0.6, "renda_variavel": 0.3},
}
_LIQUIDEZ_RAPIDA = {"diaria", "d+1"}


def _normaliza(texto: str) -> str:
    import unicodedata  # noqa: PLC0415

    nfkd = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _mapa_objetivo(objetivo: str) -> dict[str, float] | None:
    """Casa o objetivo (sem acento) por igualdade ou continencia com as chaves.

    Tolera variacoes como 'Construir reserva de emergencia' -> 'reserva de
    emergencia'.
    """
    alvo = _normaliza(objetivo)
    if alvo in _ADERENCIA_OBJETIVO:
        return _ADERENCIA_OBJETIVO[alvo]
    for chave, mapa in _ADERENCIA_OBJETIVO.items():
        if chave in alvo:
            return mapa
    return None


class SuitabilidadeInput(BaseModel):
    objetivo: str | None = Field(
        default=None, description="objetivo do cliente (ex.: 'reserva de emergencia')"
    )
    valor_disponivel: float | None = Field(
        default=None, ge=0, description="quanto o cliente tem para aplicar"
    )


class SuitabilidadeTool:
    name = "avaliar_suitability"
    description = (
        "Lista os produtos financeiros adequados ao perfil de risco do cliente e "
        "ranqueados pelo objetivo informado. Use ANTES de qualquer recomendacao: "
        "so e permitido sugerir produtos que esta ferramenta marcar como elegiveis. "
        "Retorna elegiveis (com aderencia) e bloqueados (com motivo)."
    )
    input_model = SuitabilidadeInput

    def __init__(
        self, perfil: PerfilInvestidor, produtos: list[ProdutoFinanceiro]
    ) -> None:
        self._perfil = perfil
        self._produtos = produtos

    def _aderencia(
        self, produto: ProdutoFinanceiro, objetivo: str | None, horizonte: int | None
    ) -> float:
        score = 0.5  # neutro quando nao ha objetivo mapeado
        if objetivo:
            mapa = _mapa_objetivo(objetivo)
            if mapa:
                score = mapa.get(produto.classe, 0.3)
        # Horizonte curto penaliza baixa liquidez; horizonte longo tolera.
        if horizonte is not None and horizonte <= 12:
            if (produto.liquidez or "").lower() not in _LIQUIDEZ_RAPIDA:
                score *= 0.5
        return round(score, 3)

    def run(self, args: SuitabilidadeInput) -> Insight:
        perfil = self._perfil
        elegiveis: list[dict] = []
        bloqueados: list[dict] = []

        for p in self._produtos:
            if not perfil_atende(perfil.perfil_risco, p.risco):
                bloqueados.append(
                    {
                        "produto_id": p.produto_id,
                        "nome": p.nome,
                        "motivo": f"risco '{p.risco}' acima do perfil '{perfil.perfil_risco}'",
                    }
                )
                continue
            if (
                args.valor_disponivel is not None
                and p.aplicacao_minima is not None
                and p.aplicacao_minima > args.valor_disponivel
            ):
                bloqueados.append(
                    {
                        "produto_id": p.produto_id,
                        "nome": p.nome,
                        "motivo": (
                            f"aplicacao minima R$ {p.aplicacao_minima:.2f} acima do "
                            f"disponivel R$ {args.valor_disponivel:.2f}"
                        ),
                    }
                )
                continue
            elegiveis.append(
                {
                    "produto_id": p.produto_id,
                    "nome": p.nome,
                    "classe": p.classe,
                    "rentabilidade_aa": p.rentabilidade_aa,
                    "rentabilidade_desc": p.rentabilidade_desc,
                    "aplicacao_minima": p.aplicacao_minima,
                    "aderencia": self._aderencia(p, args.objetivo, perfil.horizonte_meses),
                }
            )

        elegiveis.sort(key=lambda d: d["aderencia"], reverse=True)

        # referencias = ids elegiveis: o teto que a politica usa para barrar
        # recomendacoes fora da lista.
        referencias = [d["produto_id"] for d in elegiveis]
        # Proveniencia: rentabilidade e aplicacao minima dos elegiveis sao valores
        # reais do catalogo que o agente pode citar (verificador autoriza).
        numeros: list[float] = []
        for d in elegiveis:
            if d["rentabilidade_aa"] is not None:
                numeros.append(float(d["rentabilidade_aa"]))
            if d["aplicacao_minima"] is not None:
                numeros.append(float(d["aplicacao_minima"]))

        if elegiveis:
            nomes = ", ".join(d["nome"] for d in elegiveis[:3])
            resumo = (
                f"{len(elegiveis)} produto(s) adequado(s) ao perfil "
                f"'{perfil.perfil_risco}'. Mais aderentes ao objetivo: {nomes}. "
                f"{len(bloqueados)} bloqueado(s) por risco ou aplicacao minima."
            )
        else:
            resumo = (
                f"Nenhum produto do catalogo e adequado ao perfil "
                f"'{perfil.perfil_risco}' com os filtros informados."
            )

        return Insight(
            fonte=self.name,
            resumo=resumo,
            numeros=numeros,
            referencias=referencias,
            dados={"elegiveis": elegiveis, "bloqueados": bloqueados},
        )
