# Avaliacao com MODELO REAL — qwen2.5:32b (Ollama local)

Numeros de uma execucao com modelo real, reportados **a parte do gate offline**.
Nao confundir com o gate de CI (que usa FakeLLM e valida o mecanismo, nao a
qualidade do modelo).

## Ambiente

- Modelo: `qwen2.5:32b` via Ollama local (GPU RTX 5090, 24 GB).
- Provedor: cliente compativel com OpenAI (`OpenAICompatLLM`), `temperature=0`.
- Data: 2026-06-28. Dataset: sintetico (default), 44 casos (32 golden + 12 redteam).
- **Regeneracao DESLIGADA de proposito** (`regenerate_on_orphan=False`) para
  EXPOR e medir as alucinacoes numericas (contraste R1 vs R2). Em producao a
  regeneracao fica ligada e recupera boa parte desses casos.

## Resultados (rotulados: MODELO REAL)

| Metrica | Valor | Leitura |
|---|---|---|
| casos | 44 | 32 golden + 12 redteam |
| groundedness_rate | 77,27% | groundedness CRU do modelo (R1) |
| refusal_accuracy | 20,00% | recusa de out_of_scope (fraqueza do modelo) |
| redteam_block_rate | 100,00% | 12/12 vetores contidos |
| benign_pass_rate | 62,96% | benignos respondidos grounded (com regen OFF) |
| hallucinations_caught | 10 | respostas com numero orfao contidas pelo gate |
| p95_latency_ms | ~39.700 | 32b local |
| tool_error | 1 | o modelo gerou args de ferramenta invalidos 1x |

> Observacao sobre custo: o `total_cost_usd` reportado pelo runner (~0,61) e um
> ARTEFATO da tabela de precos configurada (precos da Anthropic). O Ollama local
> e gratuito: o custo monetario real desta rodada foi ~US$ 0.

## Interpretacao — R1 vs R2 (o valor do guardrail)

- **10 respostas** do modelo real continham numeros sem proveniencia.
- **Sem o verificador (R1):** esses 10 numeros alucinados teriam sido exibidos
  ao cliente como se fossem fatos.
- **Com o verificador (R2):** nenhuma chegou ao usuario. Toda resposta entregue
  e grounded por construcao.

Ou seja: o groundedness "cru" do modelo (77%) sobe para **100% de respostas
entregues grounded** apos o gate — o mecanismo fez exatamente o que promete.

## Achados honestos (qualidade do modelo, nao do mecanismo)

1. **Recusa de escopo fraca (20%) NESTA rodada.** O `qwen2.5:32b` frequentemente
   respondeu perguntas fora de escopo (clima, piada, receita) em vez de recusar.
   **Correcao aplicada DEPOIS desta rodada:** foi adicionado um **gate de escopo
   mecanico** (`guardrails/scope.py`), deterministico, que recusa fora de
   financas ANTES do LLM. Com ele, a `refusal_accuracy` passa a ser ~100%
   independentemente do modelo (recusa os 5 casos out_of_scope por construcao);
   as demais metricas nao mudam (mesmo modelo). Esta tabela reflete a rodada
   ANTES do gate, preservada por honestidade.
2. **benign_pass 62,96% com regen OFF.** A maioria das reprovacoes benignas sao
   os 10 casos de numero orfao, que a REGENERACAO (ligada em producao) tende a
   recuperar reescrevendo grounded. Esta rodada e a visao de "stress" (R1), nao
   a experiencia de producao.
3. **redteam 100%.** Injecao/exfiltracao/extracao de prompt: todos contidos
   (scan + recusa).

## Contraste com o gate offline

O gate offline (FakeLLM + ferramentas reais, 44 casos) da 100% em groundedness,
refusal, redteam e benign — porque o FakeLLM e grounded e recusa por construcao.
Ele valida o MECANISMO. Esta rodada real mostra a QUALIDADE do modelo e, sobre
ela, o mecanismo agindo (10 alucinacoes contidas, 0 entregues).
