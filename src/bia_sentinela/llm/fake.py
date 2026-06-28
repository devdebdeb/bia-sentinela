"""LLM determinístico para testes/eval offline.

`script` é uma fila de `LLMResponse` consumida por chamada; alternativamente,
`responder(messages) -> LLMResponse` fornece a lógica.
"""

from __future__ import annotations

from collections.abc import Callable

from .base import LLMResponse, Message


class FakeLLM:
    def __init__(
        self,
        script: list[LLMResponse] | None = None,
        responder: Callable[[list[Message]], LLMResponse] | None = None,
        model: str = "fake-model",
    ) -> None:
        self._script = list(script or [])
        self._responder = responder
        self._model = model
        self.calls: list[list[Message]] = []

    def complete(self, messages, *, system=None, tools=None) -> LLMResponse:  # noqa: ANN001
        self.calls.append(list(messages))
        if self._responder is not None:
            r = self._responder(messages)
        elif self._script:
            r = self._script.pop(0)
        else:
            r = LLMResponse(text="(sem resposta scriptada)", model=self._model)
        if r.model == "unknown":
            r.model = self._model
        return r
