"""LLMClient sobre qualquer endpoint compatível com a API da OpenAI.

Um único cliente atende provedores gratuitos e pagos que falam o protocolo da
OpenAI: Groq, Google Gemini (endpoint compat), Ollama local, OpenRouter, etc.
Troca-se de provedor mudando `base_url`/`model`/`api_key` — nada de codigo.

Como no cliente Anthropic, o turno `assistant` com `tool_calls` e reconstruido a
partir da memoria das chamadas emitidas (`_tool_use_memory`), porque o runtime
mantem na conversa apenas os `tool_result`. O import da SDK e lazy.
"""

from __future__ import annotations

import json
import time
from typing import Any

from .base import LLMResponse, Message, ToolCall


class OpenAICompatLLM:
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str = "https://api.groq.com/openai/v1",
        max_tokens: int = 1024,
        timeout_s: float = 30.0,
        max_retries: int = 3,
        temperature: float = 0.0,
    ) -> None:
        try:
            import openai  # noqa: PLC0415  (lazy: opcional via extra [openai])
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Pacote 'openai' não instalado. Use: pip install bia-sentinela[openai]"
            ) from exc
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_s)
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._temperature = temperature
        # Memoria de tool_calls com VIDA POR TURNO (ver _reset_memory_if_new_turn).
        self._tool_use_memory: dict[str, dict[str, Any]] = {}

    def _reset_memory_if_new_turn(self, messages: list[Message]) -> None:
        """Zera a memoria de tool_calls na 1a chamada de um turno.

        A memoria e populada em `_parse` e lida em `_build_messages` das chamadas
        SEGUINTES do MESMO turno. A 1a chamada de um turno nao traz mensagem
        role="tool"; resetar ali impede acumulo e colisao de ids entre turnos —
        o harness e cacheado via `st.cache_resource`, compartilhado entre sessoes.
        Limitacao residual: nao protege contra turnos concorrentes no mesmo objeto
        cacheado; o fix robusto e tornar a reconstrucao stateless (ver CHANGELOG).
        """
        if not any(m.role == "tool" for m in messages):
            self._tool_use_memory = {}

    def complete(self, messages, *, system=None, tools=None) -> LLMResponse:  # noqa: ANN001
        import openai  # noqa: PLC0415

        self._reset_memory_if_new_turn(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,  # 0 = saida reproduzivel
            "messages": self._build_messages(messages, system=system),
        }
        if tools:
            payload["tools"] = self._to_openai_tools(tools)

        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                resp = self._client.chat.completions.create(**payload)
                return self._parse(resp)
            except (
                openai.APITimeoutError,
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APIStatusError,
            ) as exc:
                last_exc = exc
                time.sleep(min(2**attempt, 8))  # backoff exponencial limitado
        raise RuntimeError(f"LLM falhou após {self._max_retries} tentativas") from last_exc

    @staticmethod
    def _to_openai_tools(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Converte as specs do registry para o formato 'function' da OpenAI."""
        return [
            {
                "type": "function",
                "function": {
                    "name": s["name"],
                    "description": s.get("description", ""),
                    "parameters": s.get("input_schema", {}),
                },
            }
            for s in specs
        ]

    def _build_messages(
        self, messages: list[Message], *, system: str | None
    ) -> list[dict[str, Any]]:
        """Converte a conversa do harness para o formato de chat da OpenAI.

        Mensagens `tool` consecutivas viram um turno assistant(tool_calls) seguido
        das mensagens role='tool', reconstruindo o turno do assistente a partir da
        memoria. O system prompt entra como a primeira mensagem.
        """
        out: list[dict[str, Any]] = []
        if system:
            out.append({"role": "system", "content": system})

        bloco_tools: list[Message] = []

        def _flush() -> None:
            if not bloco_tools:
                return
            tool_calls = []
            for m in bloco_tools:
                memo = self._tool_use_memory.get(m.tool_call_id or "", {})
                tool_calls.append(
                    {
                        "id": m.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": memo.get("name", "ferramenta"),
                            "arguments": json.dumps(memo.get("input", {})),
                        },
                    }
                )
            out.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            for m in bloco_tools:
                out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
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
        choice = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, args=args))
            self._tool_use_memory[tc.id] = {"name": tc.function.name, "input": args}

        usage = getattr(resp, "usage", None)
        return LLMResponse(
            text=(choice.content or "").strip(),
            tool_calls=tool_calls,
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
            model=self._model,
        )
