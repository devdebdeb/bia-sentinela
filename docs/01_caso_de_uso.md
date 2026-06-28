# 01 — Caso de uso, persona, arquitetura e anti-alucinacao

## O problema

Assistentes financeiros com IA generativa sao uteis, mas perigosos quando
**inventam numeros** ou **recomendam produtos fora do perfil** do cliente. Em
financas, um numero errado dito com confianca e um risco real (decisao de
investimento, falsa sensacao de seguranca). O desafio "Bia do Futuro" (DIO) pede
um agente proativo; este projeto trata a parte dificil: faze-lo **confiavel**.

## Persona e tom de voz

**BIA Sentinela** — assistente financeira pessoal, proativa e consultiva.
- **Proativa:** ao abrir, ela ja varre os dados e antecipa o que importa (gastos
  fora do padrao, caixa parado, possivel golpe de PIX, produtos adequados) — nao
  espera a pergunta.
- **Tom:** claro, direto, em portugues do Brasil; explica a origem dos numeros
  ("segundo suas transacoes...", "na simulacao..."); nunca promete retorno
  garantido; recusa com educacao o que esta fora de financas.
- **Honesta:** quando nao pode confirmar um numero, diz que nao pode — em vez de
  arriscar.

## Capacidades (ferramentas)

Cada capacidade e uma ferramenta deterministica (contrato Tool -> Insight). O LLM
escolhe qual chamar; os numeros nascem nelas.

| Ferramenta | O que faz |
|---|---|
| `resumo_gastos` | gastos por categoria, a partir das transacoes reais |
| `detectar_anomalias` | picos atipicos (IsolationForest) + degraus de assinatura |
| `avaliar_suitability` | produtos adequados ao perfil, ranqueados por objetivo |
| `simular_meta` | probabilidade de atingir uma meta (juros compostos + Monte Carlo) |
| `consultar_glossario` | define termos financeiros (base de conhecimento) |
| `consultar_produto` | detalha um produto do catalogo |
| `detectar_fraude_pix` | risco de golpe em transferencias PIX (modelo supervisionado) |

## Arquitetura

Tres frentes, integradas por um harness:

```
                 +------------------- HARNESS (runtime) -------------------+
entrada do  -->  | sanitiza + scan de injeção                              |
usuario          | gate de escopo (recusa fora de financas)               |
                 | loop: LLM escolhe ferramentas                          |
                 |    -> args validados (Pydantic) -> calculo determinista |  <- DADOS
                 |    -> resultado empacotado como dado inerte             |
                 | resposta final do LLM                                   |  <- GENAI
                 | verificador de proveniencia numerica (regenera 1x)     |
                 | gate de politica (promessas, suitability)              |  <- CYBERSEC
                 | sanitiza saida + log estruturado                       |
                 +-------------------- TurnResult -------------------------+
```

- **Dados** (`data/`, `tools/`): camada pura/determinista (seed fixa). E onde os
  numeros nascem e onde mora a confianca, com cobertura de testes alta.
- **GenAI** (`llm/`, `harness/`, `prompts.py`): orquestracao por tool-calling,
  independente de provedor (Groq, Ollama, Gemini, Anthropic, ou FakeLLM em teste).
- **Cybersec** (`security/`, `guardrails/`): redacao de PII, defesa contra prompt
  injection, segredos via ambiente, gates de verificacao/politica/escopo.

## Estrategia anti-alucinacao (defesa em camadas)

1. **Origem mecanica dos numeros.** Nenhuma ferramenta exposta ao LLM aceita
   numeros do exterior; todo valor vem dos dados injetados ou do calculo. O LLM
   nao tem como "originar" um numero por uma ferramenta.
2. **Verificador de proveniencia** (`guardrails/verifier.py`): todo numero na
   resposta final precisa rastrear a um `Insight` (ou a pergunta do usuario).
   Numero orfao -> uma tentativa de regeneracao com os fatos reapresentados ->
   se persistir, a resposta e bloqueada por uma mensagem segura.
3. **Gate de politica** (`guardrails/policy.py`): bloqueia promessas proibidas
   ("retorno garantido") e recomendacao de produto fora do conjunto elegivel
   pela suitability.
4. **Gate de escopo** (`guardrails/scope.py`): recusa, de forma deterministica,
   pedidos fora de financas — inclusive pedidos MISTOS (financa + fora de escopo).
5. **Dado externo e inerte** (`security/injection.py`): tudo que vem de
   ferramentas/documentos e empacotado e tratado como dado, nunca como instrucao.

O efeito medido: mesmo quando o modelo real produz um numero sem proveniencia, o
verificador o contem antes de chegar ao usuario (ver `04_metricas.md`).
