# 02 — Base de conhecimento

Escopo da base de conhecimento: **lookup deterministico** (sem RAG vetorial),
por decisao de projeto. O corpus aqui e pequeno e fechado, entao um lookup e mais
simples, auditavel e sem dependencias pesadas — e mantem a regra de que numeros so
vem de ferramenta.

## Fontes e estrutura

### 1. Glossario financeiro (estatico)
- **Arquivo:** `data/knowledge/glossario.json`.
- **Estrutura:** mapa `termo -> definicao` (JSON), ~22 termos em PT-BR (CDB,
  Tesouro Selic, CDI, liquidez, perfil de risco, suitability, reserva de
  emergencia, diversificacao, volatilidade, Monte Carlo, caixa ocioso, anomalia...).
- **Conteudo:** definicoes conceituais, sem cifras especificas (para nao
  introduzir numeros sem contexto).
- **Acesso:** ferramenta `consultar_glossario` (`tools/conhecimento.py`), com
  casamento robusto (sem acento, por continencia). Retorna um `Insight` com a
  definicao; e tratada como dado inerte pelo harness.

### 2. Catalogo de produtos
- **Fonte:** `data/raw/produtos_financeiros.json` (sintetico) ou
  `data/dio/produtos_financeiros.json` (real da DIO, via adaptador).
- **Estrutura:** lista de `ProdutoFinanceiro` (id, nome, classe, risco minimo,
  rentabilidade, liquidez, aplicacao minima). Quando a rentabilidade e relativa
  (ex.: "100% da Selic", dados da DIO), fica em `rentabilidade_desc`.
- **Acesso:** `consultar_produto` (detalha um produto) e `avaliar_suitability`
  (filtra por perfil e ranqueia por objetivo). A suitability define o TETO do que
  pode ser recomendado.

### 3. Dataset de fraude PIX (treino do detector)
- **Fonte:** `andremessina/pix-fraud-br` (HuggingFace), dataset autoral —
  SINTETICO, derivado do PaySim, licenca ODC-BY.
- **Amostra comitada:** `data/pix_sample/pix_fraud_sample.csv` (~6k linhas,
  estratificada; ver `data/pix_sample/README.md` para composicao e atribuicao).
- **Uso:** treina o modelo de `detectar_fraude_pix` (sklearn, seed fixa). Nao e
  consultado como texto; e dado de treino/avaliacao.

## Por que lookup e nao RAG vetorial

O conhecimento e curado e pequeno; um lookup deterministico:
- e auditavel (a definicao retornada e exatamente a do arquivo);
- nao adiciona infra (Chroma/FAISS, embeddings, servidor);
- nao abre porta para o modelo "interpretar" o conhecimento como instrucao.

## Caminho de evolucao (se o corpus crescer)

Migrar para RAG por embeddings (Chroma/FAISS sobre glossario + catalogo +
documentos), tratando o conteudo recuperado sempre como dado inerte
(`security/injection.wrap_untrusted`). Para alinhar os embeddings de retrieval ao
dominio financeiro, ha prior art aberta do Santander AI Lab:
`SantanderAI/linear-adapter-trainer` (adapters de embedding por triplet loss).
