"""LLMClient de produção sobre a SDK da Anthropic.

Timeout explícito, retry com backoff em erros transitórios, chave só do
ambiente. O import da SDK é lazy para o harness e os testes rodarem sem a
dependência instalada.

Reconstrucao de turnos: o runtime mantem na conversa apenas o resultado das
ferramentas (`role="tool"`), sem reanexar o turno `assistant` com os blocos
`tool_use` — o que basta para o FakeLLM, mas a API da Anthropic exige o par
tool_use/tool_result. Este cliente reconstroi esse par a partir da memoria das
tool_calls que ele mesmo emitiu (`_tool_use_memory`).
"""

from __future__ import annotations

import time
from typing import Any

from .base import LLMResponse, Message, ToolCall


class AnthropicLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        max_tokens: int = 1024,
        timeout_s: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        try:
            import anthropic  # noqa: PLC0415  (lazy: opcional em dev/test)
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Pacote 'anthropic' não instalado. Use: pip install bia-sentinela[llm]"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s)
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        # id da tool_call -> {name, input}; alimentado a cada resposta com tools.
        self._tool_use_memory: dict[str, dict[str, Any]] = {}

    def complete(self, messages, *, system=None, tools=None) -> LLMResponse:  # noqa: ANN001
        import anthropic  # noqa: PLC0415

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": self._build_messages(messages),
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.messages.create(**payload)
                return self._parse(resp)
            except (
                anthropic.APITimeoutError,
                anthropic.RateLimitError,
                anthropic.APIStatusError,
            ) as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 8))  # backoff exponencial limitado
        raise RuntimeError(f"LLM falhou após {self._max_retries} tentativas") from last_exc

    def _build_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Converte a conversa do harness para o formato de mensagens da API.

        Mensagens `tool` consecutivas viram um par assistant(tool_use) +
        user(tool_result), reconstruindo o turno do assistente a partir da
        memoria das tool_calls emitidas. Mensagens normais passam direto.
        """
        out: list[dict[str, Any]] = []
        bloco_tools: list[Message] = []

        def _flush() -> None:
            if not bloco_tools:
                return
            tool_use, tool_result = [], []
            for m in bloco_tools:
                memo = self._tool_use_memory.get(m.tool_call_id or "", {})
                tool_use.append(
                    {
                        "type": "tool_use",
                        "id": m.tool_call_id,
                        "name": memo.get("name", "ferramenta"),
                        "input": memo.get("input", {}),
                    }
                )
                tool_result.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content,
                    }
                )
            out.append({"role": "assistant", "content": tool_use})
            out.append({"role": "user", "content": tool_result})
            bloco_tools.clear()

        for m in messages:
            if m.role == "tool":
                bloco_tools.append(m)
                continue
            _flush()
            out.append({"role": m.role, "content": m.content})
        _flush()
        return out

    def _parse(self, resp: Any) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                args = dict(block.input)
                tool_calls.append(ToolCall(id=block.id, name=block.name, args=args))
                self._tool_use_memory[block.id] = {"name": block.name, "input": args}
        return LLMResponse(
            text="\n".join(text_parts).strip(),
            tool_calls=tool_calls,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            model=self._model,
        )
