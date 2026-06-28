# AGENTS.md — Contexto do projeto BIA Sentinela

Contexto para quem for desenvolver neste repositório. Leia antes de escrever
código.

## O que é
Agente financeiro proativo com IA generativa, em três frentes:
- Dados: análise exploratória, feature engineering e a narrativa que define o
  que o agente antecipa (`src/bia_sentinela/data/`, `analysis/`).
- GenAI: orquestração por tool-calling e verificação de proveniência
  (`harness/`, `guardrails/`, `llm/`).
- Cybersec: redação de PII, defesa contra prompt injection, segredos via
  ambiente (`security/`, `config/`).

## Regra central
O LLM não origina números nem recomenda fora do perfil. Todo valor exibido
nasce na camada determinística (`data/`, `tools/`) e passa pelo verificador
(`guardrails/verifier.py`). Para um número novo, escreva uma ferramenta que o
calcule — não peça ao modelo.

## Estrutura
```
src/bia_sentinela/
  schemas.py        contratos de dados + Insight + TurnResult
  prompts.py        system prompt versionado (PROMPT_VERSION)
  data/             generator, ingestion, profiling, features
  observability/    logging JSON + redação PII + trace
  security/         redaction, injection, sanitize
  llm/              base (Protocol), fake, anthropic_client
  tools/            base (registry + validação), example
  guardrails/       verifier, policy
  harness/          context + runtime
  eval/             dataset, metrics, judge, run_eval, harness_factory
analysis/           eda.py, data_story.md, figures/, eda_report.json
config/settings.py  config via env, sem segredos
data/raw/           dados (sintéticos reproduzíveis; troque pelos reais)
data/synthetic/     dados rotulados p/ medir recall de anomalia
docs/               data_dictionary.md, plano do projeto
tests/              suíte (segurança, verificador, política, smoke, dados)
eval_data/          golden + red-team (JSONL)
```

## Convenções
- Python 3.11+, tipado. Lint: `ruff`. Testes: `pytest`.
- A camada de cálculo (`data/`, `tools/`) é pura e determinística (seed fixa);
  é onde mora a confiança nos números, com cobertura de testes alta.
- LLM e ferramentas entram por injeção de dependência (construtor), nunca
  instanciados dentro da lógica — tudo é testável offline com `FakeLLM`.
- Prompts versionados como arquivo, nunca string solta.
- Conteúdo externo (dados, RAG) é dado inerte, jamais instrução (ver
  `security/injection.wrap_untrusted`).

## Comandos
```bash
make setup    # instala em modo editável
make test     # roda a suíte
make eval     # gate de avaliação offline (sem rede)
make lint     # ruff
PYTHONPATH=src:. python -m bia_sentinela.data.generator   # (re)gera dados
PYTHONPATH=src:. python analysis/eda.py                    # análise + figuras
```

## Onde plugar o trabalho real
As ferramentas finais (detector de anomalias com IsolationForest, suitability,
simulador de metas Monte Carlo) entram em `tools/` seguindo o contrato
`Tool -> Insight` de `tools/example.py`, reaproveitando as features de
`data/features.py`. O harness e os guardrails já estão prontos para recebê-las.

## Segurança
- Nunca commitar `.env` ou credenciais. Chaves só via `BIA_*` no ambiente.
- Nunca logar PII em claro — o logger já redige; não burle.
- Nunca adicionar uma ferramenta de cálculo livre para o LLM.
