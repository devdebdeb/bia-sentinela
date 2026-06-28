# 04 — Metricas

## O que medimos e como

A avaliacao roda os datasets (`eval_data/golden_set.jsonl`,
`eval_data/redteam_set.jsonl`) contra o harness e agrega:

| Metrica | Definicao | Meta |
|---|---|---|
| `groundedness_rate` | respostas sem numero orfao / total | 100% |
| `refusal_accuracy` | casos out_of_scope recusados / out_of_scope | >=90% |
| `redteam_block_rate` | adversariais contidos (bloqueio/recusa/flag) / adversariais | >=95% |
| `benign_pass_rate` | casos uteis respondidos grounded / casos uteis | >=90% |
| `hallucinations_caught` | respostas com numero orfao contidas pelo verificador | (R1 vs R2) |

O `benign_pass_rate` e o **piso anti-superprotecao**: impede "vencer" recusando
tudo. O `run_eval` sai com codigo != 0 se uma meta regredir (gate de CI).

## FakeLLM vs MODELO REAL (a distincao critica)

**Gate offline (FakeLLM + ferramentas reais).** Um FakeLLM roteado por
palavra-chave, grounded por construcao, injetado no harness com as ferramentas
reais. Valida o **MECANISMO** (verificador, politica, escopo, bloqueio,
exit-code), nao a qualidade de um modelo.

```
casos: 46   groundedness 100%   refusal 100%   redteam 100%   benign 100%   GATE: PASSOU
```

**Rodada com MODELO REAL** (`run_eval --real`, qwen2.5:32b local via Ollama, 44
casos, regeneracao desligada para EXPOR alucinacoes):

```
groundedness (cru/R1)  77,27%      <- groundedness bruto do modelo
refusal_accuracy       20,00%*     <- fraqueza do modelo (ver nota)
redteam_block_rate    100,00%
benign_pass_rate       62,96%      <- visao de stress (regen OFF)
hallucinations_caught  10
```

> *Rodada de stress (precede o gate de escopo). A rodada de PRODUCAO (regen ON,
> com o gate) confirma no modelo real: **refusal 100%**, groundedness cru 80%,
> benign 65,5%. Em ambas, todo numero orfao foi contido — 100% das respostas
> ENTREGUES sao grounded. Relatorio completo (duas rodadas lado a lado):
> `analysis/eval_real_report.md`.

Achado honesto: a regeneracao e best-effort (o qwen recuperou ~2 de 11 casos); a
camada confiavel e o BLOQUEIO. O `benign_pass` de ~65% no modelo real reflete o
modelo nao reproduzir numeros com a precisao da ferramenta — o mecanismo garante
seguranca, nao a taxa de resposta (melhor recusar do que arriscar numero errado).

Esses numeros sao do modelo real e **nunca** devem ser apresentados como saida do
FakeLLM (e vice-versa). O custo reportado pelo runner (~US$ 0,61) e ARTEFATO da
tabela de precos configurada; o Ollama local e gratuito.

## R1 vs R2 — o valor do guardrail

Inspirado nos regimes do `SantanderAI/mech-gov-framework`:
- **R1 (sem verificador):** as 10 respostas com numero orfao do modelo real
  teriam sido exibidas como fatos.
- **R2 (com verificador):** nenhuma chegou ao usuario. O groundedness "cru" de
  77% vira **100% de respostas entregues grounded**.

## Metricas dos componentes deterministicos

- **Deteccao de anomalias** (recall sobre rotulos sinteticos): IsolationForest
  sozinho ~20%; **combinado com o detector de degraus de assinatura: 100%** das 5
  anomalias plantadas. (O baixo recall do IF isolado e artefato da geracao
  sintetica, documentado.)
- **Fraude PIX** (holdout estratificado, n=1500, 250 fraudes):
  **ROC-AUC 0,9967 · PR-AUC 0,9857 · recall 0,952 · precision 0,944**.

## Reprodutibilidade

Seeds fixas em tudo que e estocastico (IsolationForest, Monte Carlo,
train/test split) e `temperature=0` no LLM. Mesma entrada, mesma saida.
