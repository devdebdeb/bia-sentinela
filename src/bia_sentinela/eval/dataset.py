"""Datasets de avaliação.

Cada linha JSONL é um caso. Categorias: 'factual', 'recomendacao', 'simulacao',
'out_of_scope', 'adversarial'.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalCase:
    id: str
    categoria: str
    pergunta: str
    deve_recusar: bool = False
    numeros_esperados: list[float] | None = None
    metadados: dict | None = None


def load_cases(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        cases.append(
            EvalCase(
                id=obj["id"],
                categoria=obj["categoria"],
                pergunta=obj["pergunta"],
                deve_recusar=obj.get("deve_recusar", False),
                numeros_esperados=obj.get("numeros_esperados"),
                metadados=obj.get("metadados"),
            )
        )
    return cases
