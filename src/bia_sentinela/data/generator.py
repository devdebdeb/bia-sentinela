"""Gerador de dados sintéticos.

Produz os quatro arquivos do desafio (`transacoes.csv`,
`historico_atendimento.csv`, `perfil_investidor.json`,
`produtos_financeiros.json`) com anomalias plantadas e rotuladas. Seed fixa,
reprodutível; pode ser trocado por dados reais sem afetar a análise a jusante.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
CLIENTE_ID = "cli_0001"

# Categorias de gasto e seu peso/variabilidade mensal típica.
_CATEGORIAS = {
    "moradia": (1800, 0.02),
    "alimentacao": (1200, 0.18),
    "transporte": (450, 0.25),
    "lazer": (380, 0.5),
    "saude": (300, 0.4),
    "educacao": (250, 0.1),
    "assinaturas": (120, 0.05),
    "outros": (200, 0.6),
}
RENDA_MENSAL = 9000.0


def _month_starts(n_months: int, end: date) -> list[date]:
    starts = []
    y, m = end.year, end.month
    for _ in range(n_months):
        starts.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return sorted(starts)


def gerar_transacoes(n_months: int = 12, seed: int = SEED) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    anomalias_plantadas: list[dict] = []
    months = _month_starts(n_months, date(2025, 12, 1))

    for _i, ms in enumerate(months):
        # Salário (entrada) no dia 5.
        rows.append(
            {
                "data": (ms + timedelta(days=4)).isoformat(),
                "descricao": "Salario",
                "categoria": "renda",
                "valor": round(RENDA_MENSAL, 2),
                "tipo": "credito",
                "is_anomaly": False,
            }
        )
        for cat, (base, var) in _CATEGORIAS.items():
            n_tx = rng.integers(1, 5)
            for _ in range(int(n_tx)):
                valor = -abs(rng.normal(base / n_tx, base * var / n_tx))
                dia = int(rng.integers(1, 28))
                rows.append(
                    {
                        "data": (ms + timedelta(days=dia - 1)).isoformat(),
                        "descricao": f"{cat.title()} - compra",
                        "categoria": cat,
                        "valor": round(valor, 2),
                        "tipo": "debito",
                        "is_anomaly": False,
                    }
                )

    df = pd.DataFrame(rows)

    # --- ANOMALIA 1: assinatura recorrente que dobrou de preço no mês 9 ------
    for i, ms in enumerate(months):
        preco = 39.90 if i < 8 else 89.90  # salto no 9º mês
        rows_sub = {
            "data": (ms + timedelta(days=9)).isoformat(),
            "descricao": "Streaming Premium (assinatura)",
            "categoria": "assinaturas",
            "valor": -preco,
            "tipo": "debito",
            "is_anomaly": i >= 8,
        }
        df = pd.concat([df, pd.DataFrame([rows_sub])], ignore_index=True)
        if i >= 8:
            anomalias_plantadas.append({"tipo": "assinatura_dobrou", **rows_sub})

    # --- ANOMALIA 2: pico de gasto atípico em lazer no último mês -----------
    ultimo = months[-1]
    pico = {
        "data": (ultimo + timedelta(days=20)).isoformat(),
        "descricao": "Lazer - compra atipica",
        "categoria": "lazer",
        "valor": -2200.00,
        "tipo": "debito",
        "is_anomaly": True,
    }
    df = pd.concat([df, pd.DataFrame([pico])], ignore_index=True)
    anomalias_plantadas.append({"tipo": "pico_lazer", **pico})

    df = df.sort_values("data").reset_index(drop=True)
    return df, {"anomalias_plantadas": anomalias_plantadas, "n_meses": n_months}


def gerar_perfil() -> dict:
    return {
        "cliente_id": CLIENTE_ID,
        "perfil_risco": "moderado",
        "renda_mensal": RENDA_MENSAL,
        "objetivos": ["reserva de emergencia", "aposentadoria", "viagem"],
        "horizonte_meses": 120,
        "saldo_conta": 38000.0,  # caixa parado -> oportunidade (história de dados)
    }


def gerar_produtos() -> list[dict]:
    return [
        {"produto_id": "p_cdb_liq", "nome": "CDB Liquidez Diaria", "classe": "renda_fixa",
         "risco": "conservador", "rentabilidade_aa": 10.5, "liquidez": "diaria",
         "aplicacao_minima": 100.0},
        {"produto_id": "p_tesouro_selic", "nome": "Tesouro Selic 2029", "classe": "renda_fixa",
         "risco": "conservador", "rentabilidade_aa": 10.9, "liquidez": "D+1",
         "aplicacao_minima": 100.0},
        {"produto_id": "p_cdb_pre", "nome": "CDB Prefixado 2027", "classe": "renda_fixa",
         "risco": "moderado", "rentabilidade_aa": 12.2, "liquidez": "no_vencimento",
         "aplicacao_minima": 500.0},
        {"produto_id": "p_multimercado", "nome": "Fundo Multimercado", "classe": "multimercado",
         "risco": "moderado", "rentabilidade_aa": 13.5, "liquidez": "D+30",
         "aplicacao_minima": 500.0},
        {"produto_id": "p_acoes", "nome": "Fundo de Acoes", "classe": "renda_variavel",
         "risco": "arrojado", "rentabilidade_aa": 18.0, "liquidez": "D+30",
         "aplicacao_minima": 100.0},
        {"produto_id": "p_cripto", "nome": "Fundo Cripto", "classe": "renda_variavel",
         "risco": "arrojado", "rentabilidade_aa": 25.0, "liquidez": "D+5",
         "aplicacao_minima": 100.0},
    ]


def gerar_atendimentos(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    assuntos = [
        "duvida fatura", "limite cartao", "investimentos", "app instavel", "contestacao compra"
    ]
    canais = ["app", "chat", "telefone"]
    rows = []
    for _ in range(14):
        rows.append(
            {
                "data": (date(2025, 12, 1) - timedelta(days=int(rng.integers(1, 360)))).isoformat(),
                "canal": canais[int(rng.integers(0, len(canais)))],
                "assunto": assuntos[int(rng.integers(0, len(assuntos)))],
                "resolvido": bool(rng.integers(0, 2)),
            }
        )
    return pd.DataFrame(rows).sort_values("data").reset_index(drop=True)


def gerar_tudo(
    out_dir: str | Path = "data/raw", synthetic_dir: str | Path = "data/synthetic"
) -> dict:
    out, syn = Path(out_dir), Path(synthetic_dir)
    out.mkdir(parents=True, exist_ok=True)
    syn.mkdir(parents=True, exist_ok=True)

    tx, meta = gerar_transacoes()
    # raw/ não expõe o rótulo de anomalia (simula produção); synthetic/ tem rótulo.
    tx.drop(columns=["is_anomaly"]).to_csv(out / "transacoes.csv", index=False)
    tx.to_csv(syn / "transacoes_rotulado.csv", index=False)
    (syn / "anomalias_plantadas.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    gerar_atendimentos().to_csv(out / "historico_atendimento.csv", index=False)
    (out / "perfil_investidor.json").write_text(
        json.dumps(gerar_perfil(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "produtos_financeiros.json").write_text(
        json.dumps(gerar_produtos(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"n_transacoes": len(tx), "n_anomalias": int(tx["is_anomaly"].sum())}


if __name__ == "__main__":
    info = gerar_tudo()
    print(f"Dados gerados: {info}")
