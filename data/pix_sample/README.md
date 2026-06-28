# Amostra — PIX Fraud BR

Amostra estratificada e reproduzivel do dataset **`andremessina/pix-fraud-br`**,
usada para treinar e avaliar o detector de golpe de PIX (`detectar_fraude_pix`)
de forma offline.

## Origem e licenca

- Dataset: https://huggingface.co/datasets/andremessina/pix-fraud-br
- Autor: Andre Messina.
- Natureza: **dado SINTETICO** (bootstrap estratificado + ruido gaussiano),
  derivado do **PaySim**. NAO sao transacoes reais.
- Licenca: **ODC-BY** (derivado do PaySim, CC BY-SA 4.0). Esta amostra e
  redistribuida sob ODC-BY, com atribuicao ao autor e ao PaySim.

## Composicao desta amostra

- Arquivo: `pix_fraud_sample.csv` (~6.000 linhas).
- **1.000 fraudes + 5.000 legitimas** (fraude ~16,7% nesta amostra).
- Atencao: a fraude foi **oversampled** em relacao a taxa real do dataset
  (~0,77%), para dar sinal de treino. As metricas reportadas saem de um holdout
  estratificado interno; nao confundir a taxa da amostra com a taxa real.

## Como regenerar

```
python scripts/build_pix_sample.py            # le do HuggingFace (requer rede)
python scripts/build_pix_sample.py caminho.parquet  # de um parquet local
```

Seed fixa (42): a mesma amostra e produzida a cada execucao.

## Colunas

`tipo_transacao` (chave_pix | dados_bancarios | pix_copia_e_cola), `valor_brl`,
saldos antes/depois de pagador e recebedor, `hora_dia`, `dia_util`,
`horario_noturno`, `acima_limite_noturno`, `razao_saldo_residual`,
`proporcao_valor_recebedor`, `fraude` (0/1, alvo).
