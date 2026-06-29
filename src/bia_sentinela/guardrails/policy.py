"""Gate de política aplicado à resposta final.

Regras plugáveis. Duas embutidas:

- PromessasProibidasRule: bloqueia linguagem proibida em oferta de investimento
  ("rentabilidade garantida", "sem risco", "lucro certo").
- SuitabilityRule: a resposta não pode recomendar produto fora do conjunto
  liberado pela suitability.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Protocol

from ..schemas import PolicyReport, PolicyViolation


def _ascii(texto: str) -> str:
    """Minusculas sem acento (NFKD + drop de diacriticos).

    Normaliza resposta e catalogo antes da comparacao para que 'Fundo de Acoes'
    e 'fundo de ações' casem — fechando o bypass por acento.
    """
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_PROMESSAS = re.compile(
    r"\b(rentabilidade\s+garantida|retorno\s+garantido|sem\s+risco|risco\s+zero|lucro\s+(certo|garantido)|ganho\s+garantido)\b",
    re.I,
)


class PolicyRule(Protocol):
    name: str

    def evaluate(self, response: str, *, allowed_products: list[str]) -> PolicyViolation | None: ...


class PromessasProibidasRule:
    name = "promessas_proibidas"

    def evaluate(self, response: str, *, allowed_products: list[str]) -> PolicyViolation | None:
        m = _PROMESSAS.search(response or "")
        if m:
            return PolicyViolation(rule=self.name, detail=f"linguagem proibida: '{m.group(0)}'")
        return None


class SuitabilityRule:
    """Bloqueia recomendacao de produto fora do conjunto elegivel.

    Para distinguir a mencao de um produto de texto qualquer, a regra precisa
    conhecer o catalogo (id + nome de cada produto). Sem catalogo injetado ela
    permanece inerte (comportamento seguro padrao do harness offline); com
    catalogo, marca violacao quando a resposta cita um produto conhecido cujo id
    nao esta na lista liberada pela ferramenta de suitability.
    """

    name = "suitability"

    def __init__(self, catalogo: list[tuple[str, str]] | None = None) -> None:
        # catalogo: lista de (produto_id, nome).
        self._catalogo = catalogo or []

    def evaluate(self, response: str, *, allowed_products: list[str]) -> PolicyViolation | None:
        if not self._catalogo:
            return None
        texto = _ascii(response)  # normaliza sem acento p/ casar parafrase acentuada
        permitidos = set(allowed_products)
        for produto_id, nome in self._catalogo:
            if produto_id in permitidos:
                continue  # elegivel: pode ser citado
            # Bloqueia se a resposta citar o id OU o nome do produto (sem acento).
            citado = _ascii(produto_id) in texto or (nome and _ascii(nome) in texto)
            if citado:
                return PolicyViolation(
                    rule=self.name,
                    detail=f"produto fora do conjunto elegivel: '{nome}' ({produto_id})",
                )
        return None


class PolicyGate:
    def __init__(self, rules: list[PolicyRule] | None = None) -> None:
        self._rules: list[PolicyRule] = rules or [PromessasProibidasRule(), SuitabilityRule()]

    def check(self, response: str, *, allowed_products: list[str] | None = None) -> PolicyReport:
        allowed = allowed_products or []
        violations = [
            v for r in self._rules if (v := r.evaluate(response, allowed_products=allowed))
        ]
        return PolicyReport(ok=not violations, violations=violations)
