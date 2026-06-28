"""Smoke do app Streamlit via AppTest: roda o script num runtime simulado e
confirma que abre sem excecao e renderiza a abertura proativa + chat. Pulado
quando streamlit/sklearn nao estao instalados (ex.: CI sem o extra [ui]).
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("sklearn")

from streamlit.testing.v1 import AppTest  # noqa: E402


def test_app_abre_e_renderiza_sem_excecao() -> None:
    at = AppTest.from_file("src/bia_sentinela/app.py", default_timeout=90).run()
    assert not at.exception
    titulos = [s.value for s in at.subheader]
    assert any("antecipou" in t.lower() for t in titulos)
    assert any("converse" in t.lower() for t in titulos)


def test_app_processa_pergunta_no_chat() -> None:
    at = AppTest.from_file("src/bia_sentinela/app.py", default_timeout=90).run()
    at.chat_input[0].set_value("tenho algum gasto fora do padrao?").run()
    assert not at.exception
