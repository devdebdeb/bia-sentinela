# BIA Sentinela

Assistente financeira pessoal **proativa** que **nunca inventa um numero**.
Projeto para o desafio "Bia do Futuro" (DIO).

Todo valor que a BIA mostra nasce numa camada deterministica de ferramentas e
passa por um **verificador de proveniencia** antes de aparecer. O LLM escolhe as
ferramentas e narra o resultado — ele nao origina numeros nem recomenda fora do
perfil.

## Por que

Em financas, um numero errado dito com confianca e um risco real. A maioria dos
agentes com LLM alucina valores. Aqui, a confiabilidade e **mecanica**, nao uma
promessa do modelo:

- **Numeros so de ferramenta.** Nenhuma ferramenta exposta ao LLM aceita valores
  do exterior; tudo vem dos dados injetados ou do calculo.
- **Verificador de proveniencia.** Numero sem origem e barrado antes de chegar ao
  usuario.
- **Suitability como teto.** So recomenda produtos adequados ao perfil.
- **Gates de escopo e injecao.** Recusa fora de financas e trata dado externo como
  inerte.

## Demonstracao

Abertura proativa — a BIA varre os dados e antecipa gastos atipicos, caixa
parado, golpe de PIX e produtos adequados ao perfil. Todo numero vem de uma
ferramenta deterministica.

![Abertura proativa da BIA Sentinela](docs/img/demo.png)

Chat — cada resposta traz o selo de transparencia (ferramentas usadas e resultado
da verificacao de proveniencia):

![Chat grounded com selo de verificacao](docs/img/demo_chat.png)

## Capacidades

Abertura proativa (varre os dados e antecipa) + chat. Ferramentas:

- `resumo_gastos` — gastos por categoria (dados reais).
- `detectar_anomalias` — picos atipicos (IsolationForest) + degraus de assinatura.
- `avaliar_suitability` — produtos adequados ao perfil, ranqueados por objetivo.
- `simular_meta` — probabilidade de atingir metas (juros compostos + Monte Carlo).
- `consultar_glossario` / `consultar_produto` — base de conhecimento.
- `detectar_fraude_pix` — risco de golpe em PIX (modelo supervisionado).

## Como rodar

Requer Python 3.11+.

```bash
pip install -e ".[dev,ml,ui]"      # core + testes + sklearn + streamlit
```

### Interface (Streamlit)

```bash
make run            # ou: python -m streamlit run src/bia_sentinela/app.py
```

- **Modo Demo (sem chave):** funciona offline com um FakeLLM no mesmo harness e
  guardrails. Ideal para a gravacao do pitch.
- **Modo Real:** usa o provedor configurado no `.env`.

### LLM real, de graca

Copie `.env.example` para `.env`. Opcoes (qualquer uma):

- **Groq** (hospedado, gratis, sem cartao): chave em console.groq.com.
- **Ollama** (local, offline, sem limite): `ollama pull qwen2.5:32b` e ajuste o
  `.env` para `http://localhost:11434/v1`.
- **Google Gemini** (free tier) ou **Anthropic** (pago) tambem suportados.

A chave e lida do ambiente — nunca e versionada nem logada.

### Testes e avaliacao

```bash
make test                                   # suite de testes (ou: pytest -q)

# eval offline (gate). Com 'pip install -e', rode da raiz do projeto:
python -m bia_sentinela.eval.run_eval \
    --golden eval_data/golden_set.jsonl --redteam eval_data/redteam_set.jsonl
# eval com modelo real (rotulado a parte):  ... --real
```

## Resultados

**Gate offline (FakeLLM + ferramentas reais) — valida o MECANISMO:**

```
casos: 46   groundedness 100%   refusal 100%   redteam 100%   benign 100%   GATE: PASSOU
```

**Modelo real (qwen2.5:32b local) — valida a QUALIDADE e o guardrail em acao:**
o verificador conteve **10 respostas com numeros sem proveniencia** (R1 vs R2): o
groundedness cru de 77% vira **100% de respostas entregues grounded**.

**Componentes deterministicos:** deteccao de anomalias com recall 100% (detector
combinado, sobre 5 anomalias plantadas); fraude PIX com **ROC-AUC 0,9967** em
holdout — **metricas a prevalencia sintetica (~16,7%)**; a prevalencia real
(~0,77%) a precision recalibrada cai para ~40% e ha possivel vazamento de rotulo
do PaySim. Limitacoes e a recalibracao completa em
[docs/04_metricas.md](docs/04_metricas.md#ressalvas-de-interpretacao-fraude-pix).

Detalhes e a distincao FakeLLM vs modelo real: [docs/04_metricas.md](docs/04_metricas.md).

## Dados

- **Sintetico (default):** 12 meses de transacoes reproduziveis, com anomalias
  rotuladas (`data/raw`, `data/synthetic`) — demonstra a deteccao de anomalias.
- **DIO (oficial):** os 4 arquivos do desafio em `data/dio/`, suportados via
  adaptador (selecionaveis na UI). O exemplo da DIO e enxuto (1 mes), por isso o
  sintetico e o default para mostrar a capacidade de anomalias.
- **Fraude PIX:** amostra do dataset autoral `andremessina/pix-fraud-br`
  (sintetico, derivado do PaySim, ODC-BY) em `data/pix_sample/`.

## Documentacao

- [01 — Caso de uso, arquitetura, anti-alucinacao](docs/01_caso_de_uso.md)
- [02 — Base de conhecimento](docs/02_base_conhecimento.md)
- [03 — Prompts, exemplos e edge cases](docs/03_prompts.md)
- [04 — Metricas](docs/04_metricas.md)
- [05 — Pitch (roteiro + slides)](docs/05_pitch.md)
- [Plano de implementacao](docs/00_plano_implementacao.md) · [Harness](README_HARNESS.md)

## Inspiracao

Arquitetura inspirada em praticas abertas do **Santander AI Lab**
(github.com/SantanderAI) — convergencia/inspiracao, com implementacao propria:

- `mech-gov-framework` — governanca mecanica de LLM / hard gates (nossos regimes
  R1 vs R2 na avaliacao).
- `llm_bridge` — cliente de LLM vendor-neutral (nosso `OpenAICompatLLM`).
- `autoguardrails` — guardrails dirigidos por politica + eval fixo.
- `gen-fraud-graph` — dados financeiros sinteticos com anomalias rotuladas.

## Limitacoes e proximos passos

- Recusa de escopo de modelos fracos e contida por um gate mecanico; um
  classificador de escopo dedicado pode refinar.
- Conhecimento por lookup; evoluir para RAG por embeddings se o corpus crescer.
- Deferral a um humano (caso ambiguo) como terceiro caminho alem de
  responder/bloquear.
