import pytest

from bia_sentinela.llm.base import Message

pytest.importorskip("anthropic")  # cliente real depende do extra [llm]

from bia_sentinela.llm.anthropic_client import AnthropicLLM  # noqa: E402


def _client() -> AnthropicLLM:
    # Chave dummy: __init__ nao faz rede; so testamos a montagem de mensagens.
    return AnthropicLLM(api_key="dummy-key", model="claude-test")


def test_reconstroi_par_tool_use_tool_result() -> None:
    llm = _client()
    llm._tool_use_memory["t1"] = {"name": "resumo_gastos", "input": {"categoria": "geral"}}
    msgs = [
        Message(role="user", content="quanto gastei?"),
        Message(role="tool", tool_call_id="t1", content='{"numeros":[10.0]}'),
    ]
    built = llm._build_messages(msgs)

    assert built[0] == {"role": "user", "content": "quanto gastei?"}
    # O turno assistant(tool_use) e reconstruido antes do tool_result.
    assert built[1]["role"] == "assistant"
    assert built[1]["content"][0]["type"] == "tool_use"
    assert built[1]["content"][0]["id"] == "t1"
    assert built[1]["content"][0]["name"] == "resumo_gastos"
    assert built[2]["role"] == "user"
    assert built[2]["content"][0]["type"] == "tool_result"
    assert built[2]["content"][0]["tool_use_id"] == "t1"


def test_mensagens_normais_passam_direto() -> None:
    llm = _client()
    built = llm._build_messages([Message(role="user", content="oi")])
    assert built == [{"role": "user", "content": "oi"}]
