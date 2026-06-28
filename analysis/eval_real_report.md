# Avaliacao com MODELO REAL — qwen2.5:32b (Ollama local)

Numeros de execucoes com modelo real, reportados **a parte do gate offline**. O
gate de CI usa FakeLLM e valida o MECANISMO; aqui medimos a QUALIDADE do modelo e
o mecanismo agindo sobre ela.

## Ambiente

- Modelo: `qwen2.5:32b` via Ollama local (GPU RTX 5090, 24 GB; ~12-13 tok/s).
- Cliente compativel com OpenAI, `temperature=0`. Data: 2026-06-28.
- Dataset sintetico (default). Custo reportado e ARTEFATO da tabela de precos; o
  Ollama local e gratuito (custo real ~US$ 0).

## Duas rodadas

- **Stress (regeneracao OFF):** expoe e mede as alucinacoes numericas — contraste
  R1 vs R2. (44 casos; rodada anterior a inclusao de 2 casos de gastos no golden.)
- **Producao (regeneracao ON):** comportamento real entregue ao usuario, com
  auto-conserto. (46 casos; ja com o gate de escopo mecanico.)

| Metrica | Stress (regen OFF) | Producao (regen ON) |
|---|---|---|
| casos | 44 | 46 |
| groundedness (cru) | 77,27% | 80,43% |
| refusal_accuracy | 20,00%* | **100,00%** |
| redteam_block_rate | 100,00% | 100,00% |
| benign_pass_rate | 62,96% | 65,52% |
| orfaos detectados | 10 | 11 |
| contidos pelo gate | 10 (bloqueados) | 9 bloqueados + ~2 reescritos |

> *A rodada de stress precede o gate de escopo. A rodada de producao ja o inclui
> e CONFIRMA, no modelo real, refusal de ~100% — o gate e deterministico (recusa
> antes do LLM), entao independe da qualidade do modelo.

## Leituras honestas

**1. Containment e total (a tese se sustenta).** Em ambas as rodadas, TODA
resposta com numero sem proveniencia foi contida (bloqueada ou reescrita). Nenhum
numero alucinado chegou ao usuario. O groundedness das respostas ENTREGUES e 100%
(as bloqueadas nao sao entregues). Esse e o ponto central do projeto.

**2. R1 vs R2 (valor do guardrail).** Sem o verificador (R1), as ~10 respostas
com numeros orfaos do modelo real teriam sido exibidas como fatos. Com ele (R2),
zero foram. groundedness cru ~77-80% -> 100% de respostas entregues grounded.

**3. Regeneracao e best-effort, nao garantia.** Com regen ON, o qwen2.5:32b
recuperou apenas ~2 de 11 casos: reapresentar os fatos nem sempre faz um modelo
fraco reproduzir os numeros exatamente (arredonda, troca datas/contagens). A
camada CONFIAVEL e o bloqueio; a regeneracao apenas melhora a UX quando da certo.

**4. benign_pass ~65% no modelo real.** Cerca de um terco das respostas uteis foi
bloqueada porque o modelo nao reproduziu algum numero com a precisao da
ferramenta. No FakeLLM (gate offline) o benign e 100% (grounded por construcao);
um modelo mais forte reduz esse gap. **O mecanismo garante seguranca, nao a taxa
de resposta** — e uma escolha deliberada: melhor recusar do que arriscar um numero
errado.

**5. refusal e redteam mecanicos = 100% nos dois mundos.** Gate de escopo,
verificador, politica e scan de injecao nao dependem do modelo obedecer.

## Comparacao com o gate offline

Gate offline (FakeLLM + ferramentas reais, 46 casos): 100% em groundedness,
refusal, redteam e benign — valida o MECANISMO. As rodadas reais acima mostram a
qualidade do modelo e o mecanismo contendo as falhas dele.
