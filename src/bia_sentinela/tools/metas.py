"""Ferramenta: simulacao de metas financeiras.

Projeta o patrimonio futuro de um plano de aportes por dois caminhos:
- deterministico: juros compostos sobre a taxa esperada (valor central);
- estocastico: Monte Carlo com retornos mensais normais (numpy, seed fixa),
  do qual saem probabilidade de sucesso, valor esperado e percentis.

Todas as premissas (taxa, volatilidade, n. de simulacoes) sao explicitas no
Insight. A seed e fixa: a mesma entrada gera sempre o mesmo resultado.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from ..schemas import Insight

_N_SIM = 10_000  # caminhos de Monte Carlo; fixo para reprodutibilidade


class SimularMetaInput(BaseModel):
    meta_valor: float = Field(gt=0, description="valor-alvo ao fim do horizonte")
    meses: int = Field(gt=0, le=600, description="horizonte em meses")
    aporte_mensal: float = Field(ge=0, description="quanto aplica por mes")
    aporte_inicial: float = Field(default=0.0, ge=0, description="valor ja investido hoje")
    taxa_aa: float = Field(
        default=10.5, description="retorno anual esperado em % (ex.: 10.5)"
    )
    volatilidade_aa: float = Field(
        default=4.0, ge=0, description="volatilidade anual em % (incerteza do retorno)"
    )


class SimularMetaTool:
    name = "simular_meta"
    description = (
        "Simula se um plano de aportes mensais atinge uma meta financeira no prazo, "
        "considerando juros compostos e incerteza de mercado (Monte Carlo). "
        "Retorna probabilidade de sucesso, valor esperado, percentis e as premissas. "
        "Use para metas como reserva, entrada de imovel ou aposentadoria."
    )
    input_model = SimularMetaInput

    def __init__(self, *, seed: int = 42) -> None:
        self._seed = seed

    def run(self, args: SimularMetaInput) -> Insight:
        n = args.meses
        # Conversao de taxas anuais (%) para parametros mensais.
        mu_m = (1 + args.taxa_aa / 100) ** (1 / 12) - 1
        sigma_m = (args.volatilidade_aa / 100) / np.sqrt(12)

        # Caminho deterministico (valor central, sem volatilidade).
        saldo_det = args.aporte_inicial
        for _ in range(n):
            saldo_det = saldo_det * (1 + mu_m) + args.aporte_mensal
        valor_central = round(float(saldo_det), 2)

        # Monte Carlo: cada coluna e um caminho; seed fixa.
        rng = np.random.default_rng(self._seed)
        retornos = rng.normal(mu_m, sigma_m, size=(n, _N_SIM))
        saldos = np.full(_N_SIM, float(args.aporte_inicial))
        for t in range(n):
            saldos = saldos * (1 + retornos[t]) + args.aporte_mensal
        saldos = np.maximum(saldos, 0.0)  # patrimonio nao fica negativo

        prob = round(float((saldos >= args.meta_valor).mean()) * 100, 1)
        esperado = round(float(saldos.mean()), 2)
        p10, p50, p90 = (round(float(v), 2) for v in np.percentile(saldos, [10, 50, 90]))

        resumo = (
            f"Aportando R$ {args.aporte_mensal:.2f}/mes por {n} meses (taxa "
            f"{args.taxa_aa:.1f}% a.a.), a probabilidade de atingir R$ "
            f"{args.meta_valor:.2f} e de {prob:.1f}%. Valor esperado R$ {esperado:.2f} "
            f"(faixa provavel R$ {p10:.2f} a R$ {p90:.2f})."
        )

        return Insight(
            fonte=self.name,
            resumo=resumo,
            numeros=[prob, esperado, p10, p50, p90, valor_central, round(args.meta_valor, 2)],
            referencias=[
                f"premissa:taxa_aa={args.taxa_aa}",
                f"premissa:vol_aa={args.volatilidade_aa}",
            ],
            dados={
                "probabilidade_sucesso_pct": prob,
                "valor_esperado": esperado,
                "valor_central_deterministico": valor_central,
                "percentil_10": p10,
                "percentil_50": p50,
                "percentil_90": p90,
                "premissas": {
                    "meta_valor": args.meta_valor,
                    "meses": n,
                    "aporte_mensal": args.aporte_mensal,
                    "aporte_inicial": args.aporte_inicial,
                    "taxa_aa_pct": args.taxa_aa,
                    "volatilidade_aa_pct": args.volatilidade_aa,
                    "n_simulacoes": _N_SIM,
                },
            },
        )
