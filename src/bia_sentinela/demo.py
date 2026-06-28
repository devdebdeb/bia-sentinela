"""Modo demo: harness completo sem chave de API nem rede.

A logica fica aqui (importavel e testavel); `app.py` e so a casca Streamlit.

O modo demo injeta um `FakeLLM` roteado por palavra-chave NO MESMO harness de
producao (mesmas ferramentas reais, mesmos guardrails). A narracao do FakeLLM
apenas ecoa o `resumo` do Insight da ferramenta — ou seja, todo numero exibido
continua nascendo na camada deterministica e passando pelo verificador. Serve
para a gravacao do pitch quando nao ha provedor configurado.

O scan proativo roda as ferramentas direto (sem LLM) e devolve Insights: e a
abertura "do futuro" da BIA, antecipando o que importa antes de ser perguntada.
"""

from __future__ import annotations

import re

from .data.features import caixa_ocioso, fluxo_mensal
from .data.ingestion import carregar_perfil_raw, carregar_transacoes
from .llm.base import LLMResponse, Message, ToolCall
from .schemas import Insight
from .tools.build import build_registry_from_disk

# --- Parsing best-effort para a ferramenta de metas (so no modo demo) -------- #


def _num(token: str) -> float:
    return float(token.replace(".", "").replace(",", "."))


def parse_meta(texto: str) -> dict:
    """Extrai (meta_valor, meses, aporte_mensal) de uma frase, com defaults.

    Heuristica simples: "X mil" -> X*1000; "Y anos" -> Y*12 meses; o menor valor
    monetario perto de "mes/guardando" vira o aporte. Defaults cobrem o resto.
    """
    t = texto.lower()
    mils = [_num(x) * 1000 for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*mil", t)]
    anos = re.findall(r"(\d+)\s*anos?", t)
    meses_txt = re.findall(r"(\d+)\s*mes", t)
    crus = [_num(x) for x in re.findall(r"\d+(?:[.,]\d+)?", t)]

    meta = max(mils) if mils else (max(crus) if crus else 50000.0)
    if anos:
        meses = int(anos[0]) * 12
    elif meses_txt:
        meses = int(meses_txt[0])
    else:
        meses = 60
    # aporte: numero no contexto de aporte mensal ("guardando 700", "700 por mes").
    ap = re.search(
        r"(?:guardando|aplicando|poupando|aporte\s+de|aportar)\s*r?\$?\s*(\d+(?:[.,]\d+)?)", t
    ) or re.search(r"(\d+(?:[.,]\d+)?)\s*(?:reais\s+)?(?:por\s+m[eê]s|mensa|/\s*m[eê]s)", t)
    aporte = _num(ap.group(1)) if ap else 700.0
    return {"meta_valor": meta, "meses": meses, "aporte_mensal": aporte}


# --- FakeLLM roteado por palavra-chave --------------------------------------- #

_GAT_ANOMALIA = ("estranho", "anomal", "fora do padr", "cobranca", "cobrança", "atipic")
_GAT_META = ("meta", "juntar", "guardar", "aposentad", "consigo", "simular", "poupar")
_GAT_INVEST = ("invest", "produto", "aplicar", "recomend", "reserva", "onde invisto")
_GAT_FRAUDE = ("golpe", "fraude", "pix suspeito", "esse pix", "caiu algum", "vitima", "laranja")
_GAT_RECUSA = ("ignore", "todos os clientes", "outro cliente", "system prompt", "suas instruc")
_GAT_FORA = ("tempo", "clima", "futebol", "receita de", "piada", "jogo", "esporte", "time ")
_GAT_GLOSSARIO = ("o que e", "o que significa", "o que sao", "significa", "explique", "defina")


def _resumo_da_ferramenta(conteudo: str) -> str:
    """Extrai o campo `resumo` do Insight serializado (dado da ferramenta)."""
    m = re.search(r'"resumo":\s*"([^"]*)"', conteudo)
    return m.group(1) if m else "Aqui esta o que encontrei nos seus dados."


def demo_responder(messages: list[Message]) -> LLMResponse:
    last = messages[-1]

    # Segunda passada: narra ecoando o resumo grounded da ferramenta.
    if last.role == "tool":
        return LLMResponse(text=_resumo_da_ferramenta(last.content), output_tokens=20)

    texto = last.content.lower()

    if any(k in texto for k in _GAT_RECUSA):
        return LLMResponse(
            text=(
                "Nao posso ajudar com isso. Nao acesso dados de outros clientes "
                "nem revelo minhas instrucoes internas."
            ),
            output_tokens=18,
        )
    if any(k in texto for k in _GAT_FORA):
        return LLMResponse(
            text=(
                "Isso esta fora do meu escopo, que e cuidar das suas financas "
                "pessoais. Posso ajudar com gastos, produtos adequados ou metas."
            ),
            output_tokens=16,
        )
    gloss = next((g for g in _GAT_GLOSSARIO if g in texto), None)
    if gloss:
        termo = texto.split(gloss, 1)[1].strip(" ?.!").replace("um ", "").replace("uma ", "")
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="d4", name="consultar_glossario", args={"termo": termo})],
            output_tokens=8,
        )
    if any(k in texto for k in _GAT_FRAUDE):
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="d5", name="detectar_fraude_pix", args={"top_n": 5})],
            output_tokens=8,
        )
    if any(k in texto for k in _GAT_ANOMALIA):
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="d1", name="detectar_anomalias", args={"top_n": 5})],
            output_tokens=8,
        )
    if any(k in texto for k in _GAT_META):
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="d2", name="simular_meta", args=parse_meta(texto))],
            output_tokens=8,
        )
    if any(k in texto for k in _GAT_INVEST):
        objetivo = None
        for o in ("reserva de emergencia", "aposentadoria", "viagem"):
            if o.split()[0] in texto:
                objetivo = o
                break
        return LLMResponse(
            text="",
            tool_calls=[ToolCall(id="d3", name="avaliar_suitability", args={"objetivo": objetivo})],
            output_tokens=8,
        )
    return LLMResponse(
        text=(
            "Posso te mostrar gastos fora do padrao, produtos adequados ao seu "
            "perfil ou simular uma meta financeira. O que voce prefere?"
        ),
        output_tokens=14,
    )


def build_demo_harness(data_dir: str | None = None, *, dio: bool = False):  # noqa: ANN201
    """Harness de producao com FakeLLM injetado (mesmas tools e guardrails)."""
    from config.settings import Settings  # noqa: PLC0415

    from .harness.factory import build_production_harness  # noqa: PLC0415
    from .llm.fake import FakeLLM  # noqa: PLC0415

    fake = FakeLLM(responder=demo_responder, model="demo-fake")
    base = data_dir or ("data/dio" if dio else "data/raw")
    # Settings sem chave: o llm injetado e o unico caminho.
    return build_production_harness(
        data_dir=base, settings=Settings(openai_api_key=None), llm=fake, dio=dio
    )


# --- Abertura proativa (scan dos dados -> insights, via ferramentas) --------- #


def scan_proativo(
    data_dir: str | None = None, *, dio: bool = False, seed: int = 42
) -> list[tuple[str, Insight]]:
    """Roda as ferramentas direto sobre os dados e devolve os principais insights.

    Sem LLM: numeros nascem nas ferramentas (Insight). E a antecipacao proativa
    que abre a conversa.
    """
    from pathlib import Path  # noqa: PLC0415

    base = Path(data_dir or ("data/dio" if dio else "data/raw"))
    if dio:
        from .data.dio_adapter import (  # noqa: PLC0415
            carregar_perfil_raw_dio,
            carregar_transacoes_dio,
        )
        from .tools.build import build_registry_dio  # noqa: PLC0415

        registry = build_registry_dio(base, seed=seed)
        perfil_raw = carregar_perfil_raw_dio(base / "perfil_investidor.json")
        transacoes = carregar_transacoes_dio(base / "transacoes.csv")
    else:
        registry = build_registry_from_disk(base, seed=seed)
        perfil_raw = carregar_perfil_raw(base / "perfil_investidor.json")
        transacoes = carregar_transacoes(base / "transacoes.csv")

    cards: list[tuple[str, Insight]] = []

    anomalias = registry.get("detectar_anomalias")
    cards.append(
        ("Gastos fora do padrao", anomalias.run(anomalias.input_model(top_n=3)))
    )

    # Caixa ocioso: oportunidade proativa, embrulhada como Insight (data layer).
    fluxo = fluxo_mensal(transacoes)
    co = caixa_ocioso(float(perfil_raw.get("saldo_conta", 0.0)), fluxo)
    cards.append(
        (
            "Oportunidade: caixa parado",
            Insight(
                fonte="caixa_ocioso",
                resumo=(
                    f"Voce tem cerca de R$ {co['caixa_ocioso']:.2f} parados acima de uma "
                    f"reserva de emergencia saudavel de R$ {co['reserva_recomendada']:.2f} "
                    f"(seis meses do seu gasto medio de R$ {co['gasto_medio_mensal']:.2f})."
                ),
                numeros=[co["caixa_ocioso"], co["reserva_recomendada"], co["gasto_medio_mensal"]],
                referencias=["saldo_conta"],
                dados=co,
            ),
        )
    )

    # Alerta de golpe PIX, se o detector estiver disponivel (amostra presente).
    from .tools.base import ToolError  # noqa: PLC0415

    try:
        fraude = registry.get("detectar_fraude_pix")
    except ToolError:
        fraude = None
    if fraude is not None:
        cards.append(
            ("Alerta: possivel golpe de PIX", fraude.run(fraude.input_model(top_n=3)))
        )

    suit = registry.get("avaliar_suitability")
    objetivo = (perfil_raw.get("objetivos") or [None])[0]
    cards.append(
        ("Produtos adequados ao seu perfil", suit.run(suit.input_model(objetivo=objetivo)))
    )
    return cards
