import pytest

from bia_sentinela.llm.base import Message

pytest.importorskip("openai")  # cliente depende do extra [openai]

from bia_sentinela.llm.openai_compat import OpenAICompatLLM  # noqa: E402


def _client() -> OpenAICompatLLM:
    # Chave dummy: __init__ nao faz rede; so testamos a montagem de mensagens.
    return OpenAICompatLLM(api_key="dummy-key", model="llama-test")


def test_reconstroi_turno_assistant_tool_calls() -> None:
    llm = _client()
    llm._tool_use_memory["t1"] = {"name": "detectar_anomalias", "input": {"top_n": 5}}
    msgs = [
        Message(role="user", content="gastos estranhos?"),
        Message(role="tool", tool_call_id="t1", content='{"numeros":[2200.0]}'),
    ]
    built = llm._build_messages(msgs, system="voce e a BIA")

    assert built[0] == {"role": "system", "content": "voce e a BIA"}
    assert built[1] == {"role": "user", "content": "gastos estranhos?"}
    # Turno assistant com tool_calls reconstruido antes do resultado.
    assert built[2]["role"] == "assistant"
    assert built[2]["tool_calls"][0]["id"] == "t1"
    assert built[2]["tool_calls"][0]["function"]["name"] == "detectar_anomalias"
    assert built[3]["role"] == "tool"
    assert built[3]["tool_call_id"] == "t1"


def test_memoria_reseta_em_novo_turno() -> None:
    # Simula um turno anterior que deixou memoria de tool_calls.
    llm = _client()
    llm._tool_use_memory["t1"] = {"name": "detectar_anomalias", "input": {"top_n": 5}}
    # 1a chamada de um NOVO turno (sem role="tool") -> memoria zera.
    llm._reset_memory_if_new_turn([Message(role="user", content="e agora?")])
    assert llm._tool_use_memory == {}


def test_memoria_preservada_no_mesmo_turno() -> None:
    llm = _client()
    llm._tool_use_memory["t1"] = {"name": "detectar_anomalias", "input": {"top_n": 5}}
    # Chamada do MESMO turno (traz o tool_result) -> memoria preservada.
    llm._reset_memory_if_new_turn(
        [
            Message(role="user", content="gastos estranhos?"),
            Message(role="tool", tool_call_id="t1", content='{"numeros":[2200.0]}'),
        ]
    )
    assert "t1" in llm._tool_use_memory


def test_traducao_de_specs_para_formato_function() -> None:
    specs = [{"name": "f", "description": "d", "input_schema": {"type": "object"}}]
    tools = OpenAICompatLLM._to_openai_tools(specs)
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["name"] == "f"
    assert tools[0]["function"]["parameters"] == {"type": "object"}
