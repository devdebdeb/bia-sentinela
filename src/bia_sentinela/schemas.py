"""Contratos de dados e tipos do harness.

Tudo que entra é validado contra estes contratos na fronteira. Os Insight
carregam a proveniência numérica que o verificador usa para autorizar números
na resposta final.
"""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# Contratos de domínio
class PerfilRisco(StrEnum):
    conservador = "conservador"
    moderado = "moderado"
    arrojado = "arrojado"


# Ordem de tolerância a risco, para suitability.
_RISCO_ORDEM = {PerfilRisco.conservador: 0, PerfilRisco.moderado: 1, PerfilRisco.arrojado: 2}


def perfil_atende(perfil_cliente: PerfilRisco, risco_minimo_produto: PerfilRisco) -> bool:
    """True se o perfil do cliente comporta o risco mínimo do produto."""
    return _RISCO_ORDEM[perfil_cliente] >= _RISCO_ORDEM[risco_minimo_produto]


class Transacao(BaseModel):
    data: str  # ISO-8601; validar/normalizar na ingestão
    descricao: str
    categoria: str
    valor: float = Field(description="negativo = saída, positivo = entrada")
    tipo: str


class PerfilInvestidor(BaseModel):
    cliente_id: str
    perfil_risco: PerfilRisco
    renda_mensal: float = Field(ge=0)
    objetivos: list[str] = Field(default_factory=list)
    horizonte_meses: int | None = Field(default=None, ge=0)


class ProdutoFinanceiro(BaseModel):
    produto_id: str
    nome: str
    classe: str
    risco: PerfilRisco = Field(description="perfil mínimo exigido para o produto")
    rentabilidade_aa: float | None = None
    # Rentabilidade descritiva/relativa quando nao ha um % a.a. fixo
    # (ex.: "100% da Selic", "CDI + 2%", "Variável"); usado por dados reais.
    rentabilidade_desc: str | None = None
    liquidez: str | None = None
    aplicacao_minima: float | None = None


# Saída das ferramentas determinísticas
class Insight(BaseModel):
    """Resultado de uma ferramenta determinística.

    `numeros` lista os valores que o verificador autoriza na resposta final
    (considerando todos os Insight do turno).
    """

    fonte: str = Field(description="nome da ferramenta/módulo que produziu o insight")
    resumo: str = Field(description="descrição factual e curta, sem persuasão")
    numeros: list[float] = Field(default_factory=list)
    referencias: list[str] = Field(
        default_factory=list, description="produto_ids/campos citáveis (proveniência)"
    )
    dados: dict[str, Any] = Field(default_factory=dict, description="payload estruturado bruto")


# Telemetria de chamada ao LLM
class LLMUsage(BaseModel):
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class ToolCallRecord(BaseModel):
    name: str
    ok: bool
    latency_ms: float = 0.0
    error: str | None = None


# Relatórios de guardrail
class VerificationReport(BaseModel):
    ok: bool
    checked: list[float] = Field(default_factory=list)
    orphans: list[str] = Field(default_factory=list, description="números sem proveniência")
    allowed_count: int = 0


class PolicyViolation(BaseModel):
    rule: str
    detail: str


class PolicyReport(BaseModel):
    ok: bool
    violations: list[PolicyViolation] = Field(default_factory=list)


# Resultado de um turno completo
class TurnResult(BaseModel):
    trace_id: str
    response: str
    blocked: bool = False
    block_reason: str | None = None
    verification: VerificationReport | None = None
    policy: PolicyReport | None = None
    usage: list[LLMUsage] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    latency_ms: float = 0.0
    injection_flags: list[str] = Field(default_factory=list)

    @property
    def total_cost_usd(self) -> float:
        return round(sum(u.cost_usd for u in self.usage), 6)

    @property
    def total_tokens(self) -> int:
        return sum(u.input_tokens + u.output_tokens for u in self.usage)


def new_trace_id() -> str:
    return f"trace-{uuid.uuid4().hex[:12]}"


def now_ms() -> float:
    return time.perf_counter() * 1000.0
