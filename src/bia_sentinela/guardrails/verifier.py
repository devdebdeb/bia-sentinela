"""Verificação de proveniência numérica.

Todo número na resposta final precisa rastrear a um valor produzido por uma
ferramenta (Insight) ou presente na pergunta do usuário. Número sem
proveniência ("órfão") reprova a resposta.
"""

from __future__ import annotations

import re

from ..schemas import Insight, VerificationReport

# Captura tokens numéricos: opcional R$, separadores BR/US, opcional %.
_NUMBER_RE = re.compile(r"R?\$?\s?-?\d[\d.,]*\s?%?")


def _normalize(token: str) -> float | None:
    """Converte um token textual em float, funciona em BR e US."""
    s = token.strip().lower().replace("r$", "").replace("%", "").replace(" ", "")
    s = s.lstrip("$").strip("-")
    if not s or not any(c.isdigit() for c in s):
        return None
    has_dot, has_comma = "." in s, "," in s
    try:
        if has_dot and has_comma:
            # '.' = milhar, ',' = decimal (convenção BR)
            s = s.replace(".", "").replace(",", ".")
        elif has_comma:
            s = s.replace(",", ".")
        elif has_dot:
            # Heurística: padrão de milhar (1.234 / 1.234.567) -> remove pontos.
            if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
                s = s.replace(".", "")
            # senão, trata '.' como decimal (deixa como está)
        val = float(s)
        return -val if token.strip().startswith("-") else val
    except ValueError:
        return None


def extract_numbers(text: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for m in _NUMBER_RE.finditer(text or ""):
        raw = m.group(0)
        val = _normalize(raw)
        if val is not None:
            out.append((raw.strip(), val))
    return out


def collect_allowed(insights: list[Insight], extra: list[float] | None = None) -> set[float]:
    allowed: set[float] = set()
    for ins in insights:
        allowed.update(float(n) for n in ins.numeros)
        # também aceita números presentes no resumo factual da ferramenta
        for _, v in extract_numbers(ins.resumo):
            allowed.add(v)
    if extra:
        allowed.update(extra)
    return allowed


def _matches(value: float, allowed: set[float], abs_tol: float, rel_tol: float) -> bool:
    for a in allowed:
        if abs(value - a) <= max(abs_tol, rel_tol * abs(a)):
            return True
    return False


class NumericVerifier:
    def __init__(self, abs_tol: float = 0.01, rel_tol: float = 0.005) -> None:
        self._abs_tol = abs_tol
        self._rel_tol = rel_tol

    def check(
        self,
        response: str,
        insights: list[Insight],
        user_numbers: list[float] | None = None,
    ) -> VerificationReport:
        allowed = collect_allowed(insights, extra=user_numbers)
        checked: list[float] = []
        orphans: list[str] = []
        for raw, val in extract_numbers(response):
            checked.append(val)
            if not _matches(val, allowed, self._abs_tol, self._rel_tol):
                orphans.append(raw)
        return VerificationReport(
            ok=not orphans, checked=checked, orphans=orphans, allowed_count=len(allowed)
        )
