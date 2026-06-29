"""Redação de PII.

Toda string que vai para log/telemetria passa por aqui: o sistema opera sobre
os dados mas não os registra em claro.
"""

from __future__ import annotations

import re

# PII comum no contexto financeiro brasileiro. A ORDEM importa: padroes mais
# especificos/longos antes dos mais curtos, para um nao engolir parte do outro.
# CPF aceita separadores ponto, traco OU espaco (ex.: "123 456 789 00"). CONTA
# (5-12 digitos + DV) vem antes de CARTAO; ambos antes de AGENCIA (4 + DV).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("[CNPJ]", re.compile(r"\b\d{2}[.\s]?\d{3}[.\s]?\d{3}/?\d{4}-?\d{2}\b")),
    ("[CPF]", re.compile(r"\b\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\b")),
    # Chave Pix aleatoria: UUID v4 (8-4-4-4-12 hex).
    (
        "[CHAVE_PIX]",
        re.compile(
            r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
            r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
        ),
    ),
    # Conta corrente: 5 a 12 digitos + digito verificador (ex.: "12345-6").
    ("[CONTA]", re.compile(r"\b\d{5,12}-\d\b")),
    ("[CARTAO]", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("[TELEFONE]", re.compile(r"\b(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}-?\d{4}\b")),
    # Agencia: 4 digitos + digito verificador (ex.: "1234-5").
    ("[AGENCIA]", re.compile(r"\b\d{4}-\d\b")),
]


def redact(text: str) -> str:
    """Substitui PII por tokens. A ordem dos padroes acima e significativa."""
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
