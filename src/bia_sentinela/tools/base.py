"""Registro e execução de ferramentas determinísticas.

Cada ferramenta declara um schema Pydantic de entrada, executa um cálculo puro
e retorna um `Insight` com a proveniência numérica. O LLM escolhe qual chamar;
os números nascem aqui.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from ..schemas import Insight


class Tool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]

    def run(self, args: BaseModel) -> Insight: ...


class ToolError(Exception):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"ferramenta duplicada: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"ferramenta desconhecida: {name}")
        return self._tools[name]

    def execute(self, name: str, raw_args: dict[str, Any]) -> Insight:
        """Valida os args contra o schema e executa; erros viram ToolError."""
        tool = self.get(name)
        try:
            validated = tool.input_model.model_validate(raw_args)
        except ValidationError as exc:
            raise ToolError(f"args inválidos para '{name}': {exc.error_count()} erro(s)") from exc
        return tool.run(validated)

    def specs(self) -> list[dict[str, Any]]:
        """Especificações no formato de tool-use para passar ao LLM."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_model.model_json_schema(),
            }
            for t in self._tools.values()
        ]
