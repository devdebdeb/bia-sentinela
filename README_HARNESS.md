# BIA Sentinela — Harness

Infraestrutura de execução e avaliação do agente financeiro. Não é o app: é a
camada que torna o agente testável, observável e reprodutível. A regra central
é que nenhum número aparece na resposta sem rastrear a um cálculo determinístico
— o que não rastreia é rejeitado.

## Falhas que o harness contém

| Falha | Contenção | Onde |
|-------|-----------|------|
| Número sem proveniência | Verificador rejeita órfãos | `guardrails/verifier.py` |
| Recomendação fora do perfil / promessa proibida | Gate de política | `guardrails/policy.py` |
| Prompt injection / exfiltração de PII | Dado externo inerte + scan + redação | `security/` |
| Dados inválidos | Contratos Pydantic na fronteira | `schemas.py`, `tools/base.py` |

## Fluxo de um turno

```
entrada do usuário
  → sanitização + scan de injeção              security/{sanitize,injection}
  → loop de orquestração (LLM escolhe tools)    harness/runtime
       → args validados por schema + cálculo    tools/base  (determinístico)
       → resultado empacotado como dado inerte   security/injection.wrap_untrusted
  → resposta final do LLM
  → verificador de proveniência (regenera 1x)   guardrails/verifier
  → gate de política                            guardrails/policy
  → sanitização de saída                         security/sanitize
  → TurnResult + log estruturado                 observability/logging
```

O LLM não origina números: escolhe ferramentas e narra o que elas retornam.

## Componentes

**Dados.** `schemas.py` define os contratos Pydantic; `tools/base.py` valida os
argumentos de cada ferramenta antes de executar. Os `Insight` carregam a
proveniência numérica que o verificador consome.

**GenAI.** `llm/base.py` é a interface independente de provedor (`llm/fake.py`
em teste, `llm/anthropic_client.py` em produção, com timeout e retry).
`guardrails/verifier.py` faz a verificação de proveniência. Prompts são
versionados em `prompts.py`, com `PROMPT_VERSION` logado.

**Cybersec.** `security/redaction.py` redige PII (CPF, CNPJ, cartão, email,
telefone) em todo log. `security/injection.py` trata conteúdo externo como dado
inerte e escaneia injeção. `security/sanitize.py` higieniza I/O. Segredos só via
ambiente (`config/`).

## Notas de engenharia

- Interface de LLM com fake determinístico: o harness roda offline e
  reprodutível.
- Seed fixa por execução (`harness/context.py`).
- Log JSON-lines com `trace_id`, tokens, custo, latência e resultado de
  verificação/política por turno.
- `eval/run_eval.py` sai com código ≠ 0 se uma métrica regredir; roda no CI
  (`.github/workflows/ci.yml`).
- Red-team versionado (`eval_data/redteam_set.jsonl`): injeção, exfiltração,
  vazamento de prompt.
- LLM-as-judge com rubrica explícita (`eval/judge.py`).
- LLM e ferramentas entram por injeção de dependência; lint com ruff no CI.

## Como rodar

```bash
make setup     # instala em modo editável (dev + llm)
make test      # 20 testes unitários (segurança, verificador, política, smoke)
make eval      # gate de avaliação offline (sem rede)
make lint      # ruff
```

Sem instalar nada além de pydantic/pytest, o equivalente é:

```bash
PYTHONPATH=src:. pytest -q
PYTHONPATH=src:. python -m bia_sentinela.eval.run_eval \
    --golden eval_data/golden_set.jsonl --redteam eval_data/redteam_set.jsonl
```

## Resultados de referência (rodada offline atual)

```
casos:                44
groundedness_rate:    100.00%   (meta 100%)
refusal_accuracy:     100.00%   (meta ≥90%)
redteam_block_rate:   100.00%   (meta ≥95%)
benign_pass_rate:     100.00%   (meta ≥90%)
GATE: PASSOU
```

O gate offline roda contra um `FakeLLM` roteado por palavra-chave injetado no
harness com as FERRAMENTAS REAIS (anomalias, suitability, metas, glossário,
fraude PIX). Estes números validam o mecanismo (verificador, política, bloqueio,
piso benigno, exit-code) e a fiação do harness — **não** a qualidade de um modelo
real. O `benign_pass_rate` é o piso anti-superproteção (não "vencer" recusando
tudo). Medir a qualidade do agente exige a suíte contra um LLM real (`--real`).

### Modo real e contraste R1 vs R2

`run_eval --real` roda contra o LLM de produção (`.env`) e reporta os números
**rotulados como modelo real, à parte do gate**. Roda com a regeneração
desligada para EXPOR quantas respostas o modelo real produziria com números sem
proveniência: o verificador as contém (R2), enquanto sem o guardrail (R1) elas
seriam exibidas. É a medida do valor do mecanismo, inspirada nos regimes do
`SantanderAI/mech-gov-framework`.

Bloqueio de alucinação, quando o LLM ignora a ferramenta e inventa
`R$ 9.999,00`:

```
blocked       : True
block_reason  : numeros_orfaos
orphans       : ['R$ 9.999,00']
resposta final: Não consigo confirmar com segurança os números desta resposta...
```

## Estrutura

```
src/bia_sentinela/
├── schemas.py              # contratos de dados + Insight + TurnResult
├── prompts.py              # system prompt versionado
├── observability/logging.py# log JSON + redação PII + trace
├── security/               # redaction, injection, sanitize
├── llm/                    # base (Protocol), fake, anthropic_client
├── tools/                  # base (registry + validação), example
├── guardrails/             # verifier, policy
├── harness/                # context + runtime
└── eval/                   # dataset, metrics, judge, run_eval, harness_factory
config/settings.py          # config via env, sem segredos
tests/                      # 20 testes
eval_data/                  # golden + red-team (JSONL)
.github/workflows/ci.yml    # lint + test + eval gate
```

## Próximos passos

As ferramentas reais (detecção de anomalias com IsolationForest, suitability,
simulação de metas com Monte Carlo) entram em `tools/` seguindo o contrato
`Tool -> Insight` de `tools/example.py`. A camada de cálculo é onde os números
nascem; o resto do harness já está pronto para recebê-las.
