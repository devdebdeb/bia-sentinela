"""Ferramenta: resumo de gastos por categoria (dados injetados).

Substitui o tool de exemplo `ResumoGastosTool` em producao: aquele recebia a
lista de transacoes via args do LLM — o que deixava o modelo ORIGINAR numeros,
contra a regra central. Aqui as transacoes sao injetadas por construtor; o LLM
so escolhe quantas categorias ver (e, opcionalmente, uma categoria). Os numeros
nascem na camada de dados (`features.gasto_por_categoria`).
"""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from ..data.features import gasto_por_categoria
from ..schemas import Insight


class ResumoGastosInput(BaseModel):
    top_n: int = Field(default=5, ge=1, le=20, description="quantas categorias listar")
    categoria: str | None = Field(default=None, description="filtra uma categoria especifica")


class ResumoGastosTool:
    name = "resumo_gastos"
    description = (
        "Resume os gastos do cliente por categoria (maiores primeiro), a partir "
        "das transacoes reais. Use para 'quanto gastei', 'meus gastos', 'gasto com "
        "X'. Nao recebe valores do exterior: le os dados do cliente."
    )
    input_model = ResumoGastosInput

    def __init__(self, transacoes: pd.DataFrame) -> None:
        self._tx = transacoes

    def run(self, args: ResumoGastosInput) -> Insight:
        g = gasto_por_categoria(self._tx)
        if args.categoria:
            alvo = args.categoria.strip().lower()
            g = g[g["categoria"].str.lower() == alvo]
        if g.empty:
            return Insight(
                fonte=self.name,
                resumo="Nao encontrei gastos para esse filtro.",
                numeros=[],
                dados={"gastos": []},
            )

        top = g.head(args.top_n)
        total_geral = round(float(g["total"].sum()), 2)
        gastos: list[dict] = []
        numeros: list[float] = [total_geral]
        referencias: list[str] = []
        linhas: list[str] = []
        for _, row in top.iterrows():
            total = round(float(row["total"]), 2)
            share = round(float(row["share"]) * 100, 1)
            cat = str(row["categoria"])
            numeros.append(total)
            referencias.append(f"categoria:{cat}")
            gastos.append({"categoria": cat, "total": total, "share_pct": share})
            linhas.append(f"{cat}: R$ {total:.2f} ({share:.1f}%)")

        resumo = (
            f"Gasto total de R$ {total_geral:.2f}. Maiores categorias: "
            + "; ".join(linhas)
            + "."
        )
        return Insight(
            fonte=self.name,
            resumo=resumo,
            numeros=numeros,
            referencias=referencias,
            dados={"gastos": gastos, "total_geral": total_geral},
        )
