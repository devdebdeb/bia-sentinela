"""Sanitização de I/O.

Entrada: remove caracteres de controle e limita o tamanho.
Saída: remove os delimitadores internos e redige PII residual.
"""

from __future__ import annotations

import re

from .injection import _FENCE
from .redaction import redact

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MAX_INPUT_CHARS = 4000


def sanitize_input(text: str) -> str:
    text = _CONTROL.sub("", text or "").strip()
    return text[:_MAX_INPUT_CHARS]


def sanitize_output(text: str) -> str:
    text = (text or "").replace(_FENCE, "")
    return redact(text).strip()
