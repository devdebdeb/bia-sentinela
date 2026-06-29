# Changelog

Correcoes pos-avaliacao da banca. Mudancas cirurgicas (sem alterar arquitetura);
`pytest` permanece verde.

## [Nao publicado]

### Seguranca / Observabilidade

- **Liga o logging estruturado (1.1).** `configure_logging()` agora e chamada no
  startup da UI (`app.py`) e em `build_production_harness` (`harness/factory.py`),
  antes de qualquer chamada ao LLM. Antes a funcao existia mas nunca era invocada,
  entao o logging JSON-lines + redacao de PII descritos no README nao executavam.
  Idempotente (guard `_CONFIGURED`).
- **Loga a versao do prompt (1.1).** `PROMPT_VERSION` agora entra no payload de
  `turn_start` e `turn_complete` (`harness/runtime.py`), corrigindo a divergencia
  com o docstring de `prompts.py`. Smoke test confirma JSON com `prompt_version` e
  CPF redatado (`[CPF]`).
- **Fecha o bypass do `wrap_untrusted` (1.2).** `security/injection.py` agora (a)
  neutraliza qualquer tentativa de forjar o delimitador dentro do conteudo externo
  (remove os caracteres de cerca e o rotulo) e (b) usa um **nonce por turno**
  (`uuid4`, gerado em `runtime.py`) como moldura imprevisivel — um extrato malicioso
  contendo o token de cerca nao consegue mais fechar a zona nao-confiavel e injetar
  comando. `sanitize_output` remove a moldura estatica e a do nonce. Novos testes
  em `tests/test_injection.py` (fence-inside-content e unicidade por turno).

### Documentacao / Honestidade de metricas

- **Recontextualiza as metricas de fraude PIX (1.3).** `docs/04_metricas.md` ganha
  uma secao "Ressalvas de interpretacao" com: prevalencia sintetica (~16,7%) vs
  real (~0,77%); ROC-AUC invariante a prevalencia mas PR-AUC/precision nao; a
  **recalibracao** da precision do ponto de operacao (recall 95,2%, FPR ~1,1%) de
  0,944 para **~0,40** a prevalencia real (formula de Saito & Rehmsmeier); e o
  **possivel vazamento de rotulo do PaySim** (features de saldo pos-transacao). A
  ressalva foi propagada para `README.md`, `docs/00`, `docs/05` e o docstring de
  `tools/fraude.py:avaliar_holdout` — nenhuma metrica de fraude aparece mais sem
  a nota.
