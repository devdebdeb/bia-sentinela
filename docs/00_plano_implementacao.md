# Plano de Implementacao — BIA Sentinela

Documento vivo. Junta o briefing original (as fases), as decisoes tomadas no
caminho, o status de cada fase, as licoes do Santander AI Lab a incorporar e os
lembretes para a publicacao. O briefing original esta reproduzido integralmente
no Apendice A.

---

## 1. Regras invioláveis (resumo operacional)

- O LLM NUNCA origina um numero nem recomenda fora do perfil. Todo valor nasce
  na camada deterministica (`tools/`) e e checado pelo verificador. Toda tool
  segue o contrato Tool -> Insight (args Pydantic, funcao pura, `numeros` +
  `referencias`).
- Nao reescrever a logica de `verifier.py`, `policy.py`, `runtime.py`,
  `schemas.py` nem da camada de seguranca — apenas adicionar pecas.
- Determinismo: seeds fixas em tudo que e estocastico (IsolationForest, Monte
  Carlo, e tambem `temperature=0` no LLM).
- Injecao de dependencia: LLM e tools entram por construtor.
- Honestidade: sem historico de git fabricado; nunca apresentar metricas do
  FakeLLM como desempenho de modelo real; nao inventar dados "reais"; ser claro
  sobre stubs.
- Voz: sem emoji em codigo/terminal; comentarios explicam o porque; tipado,
  PT-BR.

---

## 2. Status por fase

| Fase | Tema | Status |
|------|------|--------|
| 0 | Baseline e higiene de repo | FEITO |
| 1 | Ferramentas reais (anomalia, suitability, metas) | FEITO |
| 2 | Integracao com LLM real | FEITO |
| 2.5 | (Extra) Provedor gratuito + robustez | FEITO |
| 3 | Interface Streamlit | FEITO |
| 4 | Base de conhecimento / RAG (opcao b) | FEITO |
| 5 | Dados reais do desafio (DIO + adaptador) | FEITO |
| 6 | Avaliacao (expansao + R1/R2 + redteam) | FEITO |
| 7 | Documentacao do desafio (5 docs + README) | FEITO |
| 8 | Submissao (prep local FEITO; push/entrega = usuario) | FEITO* |

Baseline atual: 52 testes verdes, ruff limpo, eval gate offline PASSOU. Nada
commitado ainda (ver decisao D1).

---

## 3. Decisões e edições fora do briefing original

Registradas aqui para nao se perderem; cada uma foi acordada com o usuario.

### D1 — Git: init aqui, sem commitar ate a revisao final
O projeto vive dentro da pasta `tcc-gnn-fake-news` (um TCC de GNN nao
relacionado). Decisao: `git init` no `bia-sentinela/` para permitir diffs, mas
NENHUM commit ate a revisao final do usuario. A regra de "commit por fase" fica
suspensa; no fim, um (ou poucos) commits honestos. Repo-alvo da submissao:
https://github.com/devdebdeb/bia-sentinela

### D2 — Provedor de LLM gratuito (em vez de Anthropic paga)
O usuario nao quer pagar. Como o harness e agnostico de provedor, foi criado um
unico cliente compativel com a API da OpenAI (`llm/openai_compat.py`) que atende
Groq, Google Gemini, Ollama e OpenRouter trocando so `base_url`/`model`/`key`.
- Default documentado: **Groq** (gratis, sem cartao). Chave ja configurada pelo
  usuario no `.env` (ignorado pelo git).
- Limitacao real: Groq free tem teto de ~100k tokens/dia (cada turno ~6k). Para
  a demo + eval (30-50 casos), o caminho escolhido e **Ollama local**.
- GPU do usuario: RTX 5090 Laptop, 24 GB VRAM. Modelo escolhido: **`qwen2.5:32b`**
  (cabe inteiro na VRAM, tool calling forte). Receita no `.env.example`.
- `BIA_LLM_PROVIDER` seleciona o caminho; `anthropic` continua disponivel.

### D3 — `temperature=0` por padrao
Adicionado ao cliente OpenAI-compat e as settings. Alinha com o valor de
determinismo do projeto e reduz orfaos-surpresa do modelo real.

### D4 — Ajuste minimo no runtime (regeneracao anti-orfao)
Problema real descoberto no smoke com Groq: a regeneracao reenviava a pergunta
SEM os dados da ferramenta, devolvendo resposta vazia. Decisao do usuario: ajuste
minimo. Mudanca aditiva em `runtime._finalize` — a mensagem corretiva agora
reapresenta os FATOS calculados pelas ferramentas (resumos), para o modelo
reescrever grounded. Nao altera verificacao, bloqueio nem fluxo. Coberto por
`tests/test_regeneracao.py`.

### D5 — Endurecimento do prompt (anti-orfao na origem)
`prompts.py` (PROMPT_VERSION system-v1.2): instrucoes para citar so valores
monetarios das ferramentas, nunca datas/contagens/scores como digitos, usar
marcadores "-" (nao "1.", "2." que viram numero), e reproduzir percentuais com a
mesma precisao da ferramenta. Tambem: suitability passou a expor `aplicacao_minima`
em `numeros` (proveniencia legitima).

### D7 — Detector de golpe de PIX (dataset autoral do usuario)
Decisao do usuario: integrar o dataset proprio `andremessina/pix-fraud-br` (HF)
como uma NOVA ferramenta supervisionada `detectar_fraude_pix`, complementar (nao
substituta) ao `detectar_anomalias`. Da mais robustez (supervisionado + rotulos)
e peso ao projeto e ao dataset. Escopo acordado:
- Amostra estratificada COMITADA (`data/pix_sample/`, ~6k linhas, 1k fraude
  oversampled; ODC-BY com atribuicao ao autor e ao PaySim). Script reproduzivel
  em `scripts/build_pix_sample.py`. Honestidade: e SINTETICO, nao real.
- Modelo sklearn (RandomForest, seed fixa) treinado no load; metricas honestas
  num holdout estratificado: **ROC-AUC 0,9967, PR-AUC 0,9857, recall 0,952,
  precision 0,944** (n_test=1500, 250 fraudes).
- Integrado ao harness, ao scan proativo ("Alerta: possivel golpe de PIX") e ao
  modo demo. Contrato Tool->Insight; numeros nascem no modelo/dados.

### D9 — Gate de escopo mecanico + eval real (Ollama)
A rodada real completa (qwen2.5:32b local, regen OFF, 44 casos) revelou:
- **R1 vs R2:** o verificador conteve **10 respostas com numeros orfaos** (sem o
  gate iriam ao cliente; com o gate, 0 entregues). groundedness cru 77% -> 100%
  de respostas entregues grounded. redteam 100%.
- **Recusa de escopo fraca (20%)** do modelo real. Decisao do usuario: adicionar
  um **gate de escopo mecanico** (`guardrails/scope.py`, `ScopeGuardedHarness`),
  deterministico, que recusa fora de financas antes do LLM. Torna a recusa ~100%
  independente do modelo. "conta" ficou de fora por ser ambiguo ("me conta").
- **Pedido MISTO** (financa + fora de escopo, ex.: "analise minhas financas, mas
  antes uma receita de muffin de mirtilo"): o gate distingue termos FORTES
  (muffin, mirtilo, piada, futebol... -> recusam o conjunto mesmo com financa
  junto, fechando o bypass) de FRACOS/ambiguos (tempo, clima, jogo -> so sem
  financa). Evita "receita de" (ambiguo: "receita de aluguel" e financeiro),
  usando nomes de comida. Defesa em profundidade: o prompt (v1.5) tambem manda
  atender so a parte financeira e nunca produzir conteudo nao-financeiro.
- ACHADO TRATADO: o tool de exemplo `resumo_gastos` aceitava a LISTA DE
  TRANSACOES do LLM (args), deixando o LLM ORIGINAR numeros — contra a regra
  central. **Substituido** por `tools/gastos.py:ResumoGastosTool` com dados
  INJETADOS (le as transacoes reais via `features.gasto_por_categoria`); o LLM so
  passa top_n/categoria. Em producao/demo o registry usa a versao injetada; o
  tool de exemplo segue so no `build_offline_harness` (smoke). Confirmado no
  modelo real: numeros vem dos dados, grounded. Agora NENHUM tool exposto ao LLM
  aceita numeros do exterior.
- Custo reportado (~0,61) e artefato da tabela de precos; Ollama local = ~US$ 0.
- Relatorio honesto em `analysis/eval_real_report.md`.

### D8 — Dados reais da DIO (Fase 5)
A DIO forneceu os 4 arquivos (em `data/dio/`), mas com schema diferente e
transacoes minima (10 linhas, 1 mes). Decisao do usuario:
- **Sintetico (12 meses, anomalias rotuladas) segue como DEFAULT** do demo/eval/
  testes (e o que exercita a deteccao de anomalias); a **DIO entra como entrada
  oficial suportada e selecionavel** (adaptador em `data/dio_adapter.py`).
- **Adaptador** normaliza honestamente: sinal de `valor` pelo `tipo`; risco
  baixo/medio/alto -> conservador/moderado/arrojado; id gerado por slug;
  `aporte_minimo` -> aplicacao_minima; horizonte derivado das metas; saldo_conta
  = patrimonio_total (proxy, documentado).
- **schemas.py:** adicionado campo opcional aditivo `rentabilidade_desc` (a
  rentabilidade da DIO e relativa/texto, ex.: "100% da Selic"; nao viramos um %
  a.a. fixo inventado). `consultar_produto` expoe a desc no resumo (grounded).
- App tem seletor de dataset (Sintetico / DIO). Limitacao honesta: na DIO a
  deteccao de anomalias tem pouco a mostrar (1 mes) — documentar no data_story.

### D6 — Conserto do caminho Anthropic e do OpenAI-compat (tool turns)
O runtime mantem na conversa so os `tool_result`; as APIs reais exigem o turno
`assistant`/`tool_use` correspondente. Ambos os clientes reconstroem esse par a
partir da memoria das tool_calls emitidas. Feito na camada `llm/` (nao protegida).

---

## 4. Licoes do Santander AI Lab (github.com/SantanderAI)

A organizacao (Responsible AI, MLOps, graph ML, LLM eval para servicos
financeiros) tem repos que espelham nossa arquitetura — validacao forte — e
algumas ideias a incorporar. Convergencia independente, nao copia.

### Validacao (ja fazemos)
- **llm_bridge**: cliente vendor-neutral com adapters e provider `callable` ~=
  nosso `OpenAICompatLLM` + `FakeLLM`.
- **mech-gov-framework**: governanca "mecanica" com hard gates sequenciais, mock
  provider offline, dataset sintetico, eval por metricas ~= nosso harness.
- **gen-fraud-graph**: sintetico financeiro com anomalias rotuladas ~= nosso
  `data/synthetic/`. (Eles nao documentam seed; nos fixamos — estamos a frente.)

### A incorporar
- **[Fase 6] Regimes R1 vs R2 (mech-gov):** rodar o eval com o verificador
  OFF (R1) vs ON (R2) e reportar o impacto ("com guardrails: 100% grounded; sem:
  X% de orfaos passam"). Metrica demonstravel para o pitch.
- **[Fase 6] Taxonomia de ataques + benign-pass floor (autoguardrails):**
  enumerar vetores (injecao via dados, exfiltracao de PII, jailbreak de
  suitability, extracao de prompt) e reportar o piso de aprovacao benigna junto
  do block-rate (nao "vencer" recusando tudo).
- **[Polimento LLM] `finish_reason` no `LLMResponse` (llm_bridge):** detectar
  truncamento por max_tokens (possivel causa de respostas vazias).
- **[Futuro, docs] Deferral/escalonamento (mech-gov ambiguity gate):** um terceiro
  caminho alem de responder/bloquear ("nao tenho confianca, encaminho a um
  humano"). Fica como trabalho futuro para evitar scope creep.
- **[Fase 4] RAG:** o `linear-adapter-trainer` deles confirma o caminho de RAG
  por embeddings, porem pesado. Mantemos a opcao (b) (lookup de produtos +
  glossario estatico) e citamos essa referencia como evolucao possivel.

---

## 5. >>> PARA A PUBLICACAO (LinkedIn / GitHub) — NAO ESQUECER <<<

Ao publicar/postar sobre o projeto (README de raiz, post de LinkedIn, descricao
do repo), **creditar explicitamente a inspiracao no Santander AI Lab**
(github.com/SantanderAI). Enquadramento honesto: convergencia/inspiracao, nao
copia de codigo. Citar nominalmente os repos que ressoam com a nossa abordagem:

- `mech-gov-framework` — governanca mecanica / hard gates.
- `llm_bridge` — cliente de LLM vendor-neutral.
- `autoguardrails` — guardrails dirigidos por politica + eval fixo.
- `gen-fraud-graph` — sintetico financeiro com anomalias rotuladas.

Sugestao de frase: "Arquitetura inspirada em praticas abertas do Santander AI
Lab (governanca mecanica de LLM, cliente vendor-neutral, dados sinteticos
rotulados), com implementacao propria e foco em anti-alucinacao por proveniencia."

Destacar tambem o **dataset autoral** usado no projeto:
`andremessina/pix-fraud-br` (HuggingFace) — usado para treinar o detector de
golpe de PIX (`detectar_fraude_pix`). Isso da visibilidade ao dataset e reforca
a autoria. Sempre claro que e dado sintetico (derivado do PaySim, ODC-BY).

(Este lembrete tambem esta salvo na memoria persistente do assistente.)

---

## 5b. Tarefas da ETAPA FINAL (antes de fechar o projeto)

- [x] **Rodada real de PRODUCAO (regen ON):** FEITA (`run_eval --real --regen-on`,
  Ollama qwen2.5:32b, 46 casos). Resultado lado a lado em
  `analysis/eval_real_report.md`. Achado: a regeneracao recuperou so ~2 de 11
  orfaos (best-effort num modelo fraco); o BLOQUEIO conteve 100% (nenhum numero
  alucinado entregue). benign_pass ~65% (modelo nao reproduz numeros exatos).
- [x] Gate de escopo confirmado no modelo real: refusal_accuracy = **100%**.

## 6. Pendencias do usuario (acoes humanas)

- [x] Chave de API gratuita (Groq) — configurada no `.env`.
- [ ] Instalar Ollama + `ollama pull qwen2.5:32b` + `ollama serve` (para eval sem
      limite de tokens na GPU).
- [ ] Gravar o video do pitch (3 min) — roteiro sera entregue na Fase 7.
- [ ] Criar/empurrar o repo no GitHub e abrir o PR/entrega da DIO (Fase 8).
- [ ] Aprovar o commit final (ver D1).

---

## Apendice A — Briefing original (mensagem do usuario, integral)

> Você vai finalizar o projeto `bia-sentinela`. O harness, os guardrails, a
> camada de dados e o eval já existem e funcionam (20 testes verdes, ruff limpo,
> eval gate passando). O que falta é a parte VISÍVEL e demonstrável do desafio
> "Bia do Futuro" da DIO: ferramentas reais, integração com LLM real, interface,
> dados reais, eval contra modelo real, docs do desafio e higiene de submissão.
>
> ### Regras invioláveis
> - O LLM NUNCA origina um número nem recomenda fora do perfil. Todo valor nasce
>   na camada determinística (tools/) e é checado pelo verificador. Toda
>   ferramenta nova segue o contrato Tool -> Insight de tools/example.py.
> - NÃO reescreva a lógica de verifier.py, policy.py, runtime.py, schemas.py nem
>   da camada de segurança. Você adiciona peças sobre essa base; não a refatora.
> - Determinismo: seeds fixas em qualquer componente estocástico.
> - Injeção de dependência: LLM e tools entram por construtor.
>
> ### Regras de honestidade
> - NÃO fabrique histórico de git, commits backdated, nem nada que simule autoria.
> - NUNCA apresente métricas do FakeLLM como desempenho de modelo real.
> - NÃO invente os dados "reais" do desafio. Se não estiverem presentes, mantenha
>   os sintéticos e documente.
> - Seja honesto sobre stubs (ex.: SuitabilityRule).
>
> ### Fases
> - FASE 0 — Baseline e higiene de repositório. CHECKPOINT: git.
> - FASE 1 — Ferramentas reais: (1) Detecção de anomalias com IsolationForest +
>   baseline estatístico, medir recall com data/synthetic/; (2) Suitability filtra
>   por perfil e ranqueia, conjunto elegível é o teto; (3) Simulação de metas com
>   juros compostos + Monte Carlo. Registrar no ToolRegistry. Atualizar
>   SuitabilityRule para usar o conjunto elegível. Adicionar scikit-learn ao
>   pyproject se preciso.
> - FASE 2 — Integração com LLM real (AnthropicLLM atrás de BIA_ANTHROPIC_API_KEY),
>   fábrica de harness de produção, revisar prompts.py. CHECKPOINT: chave de API.
> - FASE 3 — Interface Streamlit: abertura proativa + chat, modo demo com FakeLLM,
>   modo real com chave. Comando no Makefile e README.
> - FASE 4 — Base de conhecimento / RAG. CHECKPOINT: (a) RAG leve (Chroma/FAISS)
>   ou (b) lookup de produtos + glossário estático (default se sem resposta).
> - FASE 5 — Dados reais do desafio. CHECKPOINT: se data/raw/ tem os 4 arquivos
>   reais, usar e rodar make eda; senão manter sintéticos e documentar a troca.
> - FASE 6 — Avaliação: expandir golden_set para ~30-50 casos e redteam para mais
>   vetores. Manter gate offline. Se houver chave, rodar eval contra LLM real e
>   reportar à parte, rotulado.
> - FASE 7 — Documentação do desafio (docs/): 01 caso de uso + arquitetura +
>   anti-alucinação; 02 base de conhecimento; 03 prompts; 04 métricas (FakeLLM vs
>   modelo real); 05 pitch (roteiro 3 min + slides). README.md na raiz.
> - FASE 8 — Submissão. CHECKPOINT: mecanismo de entrega da DIO (fork +
>   PR ou link). Preparar o local; criação do repo, push e PR são do usuário.
>
> ### Não faça
> - Não gravar vídeo, não criar conta/repo no GitHub, não usar chave não fornecida.
> - Não adicionar frameworks pesados nem infra. Manter simples.
> - Não adicionar dependências sem avisar e justificar.
> - Não quebrar os testes existentes nem o ruff.
>
> ### Definition of Done
> - Ferramentas reais implementadas e testadas; harness fim a fim com FakeLLM e
>   pronto para o LLM real; app Streamlit proativo; dados reais ou sintéticos
>   documentados; eval expandido (offline verde + caminho real rotulado); 5 docs
>   + README; pytest verde, ruff limpo, sem segredos, commits honestos.
