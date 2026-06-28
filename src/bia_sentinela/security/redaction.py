"""Redação de PII.

Toda string que vai para log/telemetria passa por aqui: o sistema opera sobre
os dados mas não os registra em claro.
"""

from __future__ import annotations

import re

# PII comum no contexto financeiro brasileiro.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[CPF]", re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")),
    ("[CNPJ]", re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")),
    ("[CARTAO]", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("[TELEFONE]", re.compile(r"\b(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b")),
]


def redact(text: str) -> str:
    """Substitui PII por tokens. Ordem importa: CPF/CNPJ antes de cartão."""
    if not text:
        return text
    out = text
    for token, pattern in _PATTERNS:
        out = pattern.sub(token, out)
    return out


def redact_obj(obj: object) -> object:
    """Redação recursiva em estruturas (dict/list/str) para logging seguro."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj
