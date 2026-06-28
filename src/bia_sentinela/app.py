"""Interface Streamlit da BIA Sentinela.

Casca fina: abertura proativa (scan dos dados via ferramentas) seguida de chat.
Toda a logica vive no harness e em `demo.py` — aqui so renderiza. Todo numero
exibido vem de um Insight; nada e narrado fora do harness.

Dois modos:
- Demo (sem chave): FakeLLM roteado, no mesmo harness com os guardrails reais.
- Real: provedor configurado em .env (Groq, Ollama, Gemini, Anthropic).

Rodar:  streamlit run src/bia_sentinela/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run` poe no sys.path a pasta do script, nao a raiz do projeto.
# Garante que `bia_sentinela` (src/) e `config` (raiz) sejam importaveis sem
# depender de instalacao editavel.
_ROOT = Path(__file__).resolve().parents[2]
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st  # noqa: E402

from bia_sentinela.demo import build_demo_harness, scan_proativo  # noqa: E402
from bia_sentinela.prompts import PROMPT_VERSION  # noqa: E402


@st.cache_resource
def _harness_demo(dio: bool):  # noqa: ANN202
    return build_demo_harness(dio=dio)


@st.cache_resource
def _harness_real(dio: bool):  # noqa: ANN202
    from bia_sentinela.harness.factory import build_production_harness  # noqa: PLC0415

    base = "data/dio" if dio else "data/raw"
    return build_production_harness(data_dir=base, dio=dio)


@st.cache_data
def _scan(dio: bool):  # noqa: ANN202
    return scan_proativo(dio=dio)


def _render_insight(titulo: str, insight) -> None:  # noqa: ANN001
    with st.container(border=True):
        st.markdown(f"**{titulo}**")
        st.write(insight.resumo)


def _render_turno(res) -> None:  # noqa: ANN001
    st.markdown(res.response or "_(sem resposta)_")
    selo = []
    if res.tool_calls:
        selo.append("ferramentas: " + ", ".join(t.name for t in res.tool_calls))
    if res.verification:
        selo.append("verificado: ok" if res.verification.ok else "verificado: falhou")
    if res.blocked:
        selo.append(f"bloqueado: {res.block_reason}")
    if res.injection_flags:
        selo.append("injecao: " + ", ".join(res.injection_flags))
    if selo:
        st.caption(" | ".join(selo))


def main() -> None:
    st.set_page_config(page_title="BIA Sentinela", page_icon=":bar_chart:", layout="centered")
    st.title("BIA Sentinela")
    st.caption(
        "Assistente financeira proativa. Os numeros nascem em ferramentas "
        "deterministicas e passam por um verificador anti-alucinacao antes de "
        f"aparecer. (prompt {PROMPT_VERSION})"
    )

    with st.sidebar:
        st.header("Modo")
        modo = st.radio(
            "Provedor de LLM",
            ["Demo (sem chave)", "Real (.env)"],
            help="Demo usa um FakeLLM no mesmo harness. Real usa o provedor do .env.",
        )
        st.markdown(
            "O modo Demo nao usa rede nem chave. O modo Real le `BIA_*` do `.env` "
            "(Groq, Ollama, Gemini ou Anthropic)."
        )
        st.header("Dados")
        dataset = st.radio(
            "Origem dos dados",
            ["Sintetico (12 meses)", "DIO (oficial)"],
            help=(
                "Sintetico: historico reproduzivel com anomalias rotuladas (demonstra "
                "a deteccao). DIO: os 4 arquivos reais do desafio (exemplo de 1 mes)."
            ),
        )
    dio = dataset.startswith("DIO")

    try:
        harness = _harness_demo(dio) if modo.startswith("Demo") else _harness_real(dio)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Nao foi possivel iniciar o modo Real: {exc}")
        st.stop()

    st.subheader("O que a BIA antecipou para voce")
    for titulo, insight in _scan(dio):
        _render_insight(titulo, insight)

    st.subheader("Converse com a BIA")
    if "historico" not in st.session_state:
        st.session_state.historico = []

    for papel, conteudo in st.session_state.historico:
        with st.chat_message(papel):
            if papel == "user":
                st.markdown(conteudo)
            else:
                _render_turno(conteudo)

    pergunta = st.chat_input("Ex.: tenho algum gasto fora do padrao?")
    if pergunta:
        st.session_state.historico.append(("user", pergunta))
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"), st.spinner("Analisando seus dados..."):
            res = harness.run_turn(pergunta)
            _render_turno(res)
        st.session_state.historico.append(("assistant", res))


if __name__ == "__main__":
    main()
