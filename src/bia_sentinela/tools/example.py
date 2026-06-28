"""Ferramenta de exemplo: template do contrato Tool -> Insight.

As ferramentas reais (anomalias, suitability, metas) seguem este formato.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..schemas import Insight


class ResumoGastosInput(BaseModel):
    transacoes: list[float] = Field(description="valores (negativo = saída)")
    categoria: str = "geral"


class ResumoGastosTool:
    name = "resumo_gastos"
    description = "Soma os gastos (valores negativos) de uma lista de transações por categoria."
    input_model = ResumoGastosInput

    def run(self, args: ResumoGastosInput) -> Insight:
        saidas = [v for v in args.transacoes if v < 0]
        total = round(abs(sum(saidas)), 2)
        return Insight(
            fonte=self.name,
            resumo=f"Total de gastos na categoria '{args.categoria}': R$ {total:.2f}.",
            numeros=[total],
            referencias=[f"categoria:{args.categoria}"],
            dados={"total_gastos": total, "qtde_saidas": len(saidas)},
        )
