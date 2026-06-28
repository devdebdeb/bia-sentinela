"""Gera a amostra estratificada comitada do dataset pix-fraud-br.

Fonte: https://huggingface.co/datasets/andremessina/pix-fraud-br (ODC-BY,
derivado do PaySim). O dataset completo tem 2M linhas; aqui amostramos uma
fracao pequena e reprodutivel para treino/eval offline do detector de fraude PIX,
preservando casos de fraude suficientes (a fraude e rara: ~0,77%).

A amostra COMITADA oversampla fraude em relacao a taxa real, para dar sinal de
treino; isso esta documentado no README da amostra. Metricas honestas saem de um
holdout estratificado dentro da amostra.

Uso:
    python scripts/build_pix_sample.py [caminho_ou_url_parquet]

Sem argumento, le direto do HuggingFace (requer rede + pyarrow/fsspec).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SEED = 42
N_FRAUDE = 1000
N_LEGITIMA = 5000
_URL = (
    "https://huggingface.co/datasets/andremessina/pix-fraud-br/"
    "resolve/refs%2Fconvert%2Fparquet/default/train/0000.parquet"
)
_COLS = [
    "tipo_transacao",
    "valor_brl",
    "saldo_anterior_pagador",
    "saldo_posterior_pagador",
    "saldo_anterior_recebedor",
    "saldo_posterior_recebedor",
    "hora_dia",
    "dia_util",
    "horario_noturno",
    "acima_limite_noturno",
    "razao_saldo_residual",
    "proporcao_valor_recebedor",
    "fraude",
]
_OUT = Path("data/pix_sample/pix_fraud_sample.csv")


def main() -> None:
    fonte = sys.argv[1] if len(sys.argv) > 1 else _URL
    df = pd.read_parquet(fonte, columns=_COLS)

    fraude = df[df["fraude"] == 1].sample(n=min(N_FRAUDE, int((df["fraude"] == 1).sum())),
                                          random_state=SEED)
    legitima = df[df["fraude"] == 0].sample(n=N_LEGITIMA, random_state=SEED)
    amostra = (
        pd.concat([fraude, legitima])
        .sample(frac=1.0, random_state=SEED)  # embaralha
        .reset_index(drop=True)
    )

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    amostra.to_csv(_OUT, index=False)
    print(f"amostra salva em {_OUT}: {len(amostra)} linhas, "
          f"{int(amostra['fraude'].sum())} fraudes "
          f"({amostra['fraude'].mean():.2%}).")


if __name__ == "__main__":
    main()
