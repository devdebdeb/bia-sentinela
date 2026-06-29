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

### Robustez / LLMOps

- **`_tool_use_memory` com vida por turno (2.1).** Em `llm/openai_compat.py` e
  `llm/anthropic_client.py`, a memoria de tool_calls (necessaria para reconstruir o
  turno `assistant` multi-step) era atributo de instancia que acumulava entre
  turnos; como o harness e cacheado via `st.cache_resource` (compartilhado entre
  sessoes), vazava ids de um turno/sessao para outro. Agora `complete()` chama
  `_reset_memory_if_new_turn()`, que zera a memoria na 1a chamada de cada turno
  (ausencia de mensagem `role="tool"`), preservando-a nas chamadas seguintes do
  mesmo turno. Testes novos em ambos os clientes.
  - **Tradeoff registrado:** a sugestao "variavel local em `complete()`" nao serve
    porque a memoria precisa sobreviver entre as multiplas chamadas `complete()`
    de um turno. O fix totalmente robusto (thread-safe entre sessoes concorrentes)
    seria tornar a reconstrucao *stateless* — o harness reanexar o turno
    `assistant`/`tool_use` na conversa — ou nao compartilhar o cliente entre
    sessoes. Sao mudancas maiores de arquitetura; ficam como proximo passo.

### Seguranca (guardrails)

- **SuitabilityRule resistente a acento/parafrase (2.2).** `guardrails/policy.py`
  agora normaliza resposta e catalogo com NFKD + drop de diacriticos (`_ascii`)
  antes da comparacao: 'Fundo de Acoes' (catalogo) passa a casar 'Fundo de Ações'
  (resposta), fechando o bypass por acento. A checagem por `produto_id` (ja
  existente) foi mantida e tambem normalizada. Novos testes em `tests/test_policy.py`
  (nome acentuado, citacao por id, e nao-falso-positivo em elegivel acentuado) e 2
  casos benignos no `eval_data/golden_set.jsonl` (g035 com acento, g036 descritivo
  sem nome). `run_eval` offline: 48 casos, 100% em todas as metricas, GATE PASSOU.

### Privacidade / LGPD

- **Redacao de PII financeira ampliada (2.3).** `security/redaction.py` agora cobre
  **chave Pix aleatoria (UUID)**, **agencia (4+DV)** e **conta corrente (5-12+DV)**,
  e o regex de **CPF aceita espacos** ("123 456 789 00"). A ordem dos padroes foi
  ajustada (CONTA antes de CARTAO; AGENCIA por ultimo) para um nao engolir o outro.
- **Valores financeiros fora do log (2.3).** `harness/runtime.py` deixou de logar
  `numeros=insight.numeros` (valores em claro) no evento `tool_ok`; agora loga so
  `n_numeros` (contagem). Os valores continuam fluindo ao usuario via Insight, mas
  nao sao persistidos no log. Novos testes em `tests/test_redaction.py`.

### Nice-to-have

- **Secret-scanning no CI (3.3).** Novo job `secret-scan` em
  `.github/workflows/ci.yml` roda o gitleaks (v8.18.4, historico completo) e falha
  o build se encontrar credencial commitada.
- **LLM-as-judge plugado ao eval (3.1).** `eval/judge.py` (antes orfao) agora e
  acionavel via `run_eval --judge`: roda sobre as respostas benignas entregues e
  reporta a nota media (1-5). Opt-in, best-effort (pula sem chave) e **nao** e
  gate. `run()` passou a retornar `(summary, results)` para evitar reexecutar o
  harness.
- **GIF de demo (3.2) — pendente (manual).** Requer gravacao de tela; nao
  automatizavel aqui. Roteiro sugerido: abertura proativa -> pergunta que gera
  numero -> selo "verificado: ok"; depois um caso adversarial mostrando
  "bloqueado: numeros_orfaos". Salvar em `docs/img/demo.gif` e referenciar no
  README no lugar dos screenshots estaticos.
