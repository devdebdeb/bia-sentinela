# Dicionário de Dados

Documenta os quatro artefatos de dados do desafio. A versão em `data/raw/` é
sintética e reproduzível (`src/bia_sentinela/data/generator.py`); substitua
pelos arquivos reais quando disponíveis — os contratos em `schemas.py` validam
ambos.

## `transacoes.csv`
Histórico de transações do cliente.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `data` | date (ISO-8601) | Data da transação |
| `descricao` | string | Descrição livre (ex.: "Streaming Premium (assinatura)") |
| `categoria` | string | Categoria de gasto/renda (moradia, alimentacao, ..., renda) |
| `valor` | float | Negativo = saída, positivo = entrada |
| `tipo` | string | debito \| credito |

Contrato: `schemas.Transacao`. Coluna derivada na ingestão: `mes` (período YYYY-MM).

## `perfil_investidor.json`
Perfil e preferências do cliente.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cliente_id` | string | Identificador |
| `perfil_risco` | enum | conservador \| moderado \| arrojado |
| `renda_mensal` | float | Renda mensal (R$) |
| `objetivos` | list[string] | Metas financeiras |
| `horizonte_meses` | int | Horizonte de investimento |
| `saldo_conta` | float | (auxiliar) Saldo em conta — usado em caixa ocioso |

Contrato: `schemas.PerfilInvestidor` (campo `saldo_conta` é auxiliar, fora do
contrato base).

## `produtos_financeiros.json`
Catálogo de produtos disponíveis.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `produto_id` | string | Identificador |
| `nome` | string | Nome comercial |
| `classe` | string | renda_fixa \| multimercado \| renda_variavel |
| `risco` | enum | Perfil mínimo exigido (suitability) |
| `rentabilidade_aa` | float | Rentabilidade histórica/estimada ao ano (%) |
| `liquidez` | string | diaria \| D+1 \| D+30 \| no_vencimento |
| `aplicacao_minima` | float | Aplicação mínima (R$) |

Contrato: `schemas.ProdutoFinanceiro`. Regra de suitability: produto elegível se
`perfil_atende(perfil_cliente, produto.risco)`.

## `historico_atendimento.csv`
Histórico de atendimentos anteriores.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `data` | date | Data do atendimento |
| `canal` | string | app \| chat \| telefone |
| `assunto` | string | Tema do contato |
| `resolvido` | bool | Se foi resolvido |

## Dados rotulados (`data/synthetic/`)
- `transacoes_rotulado.csv`: idem transações + coluna `is_anomaly` (ground truth).
- `anomalias_plantadas.json`: metadados das anomalias injetadas (assinatura que
  dobrou, pico de lazer). Usado para medir **recall** do detector de anomalias.
