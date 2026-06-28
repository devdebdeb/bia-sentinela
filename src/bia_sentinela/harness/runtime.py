"""Execução de um turno.

Fluxo, cada etapa logada:

  entrada
    -> sanitização + scan de injeção
    -> loop: LLM escolhe ferramentas; args validados, execução determinística,
       resultado empacotado como dado não-confiável
    -> resposta final do LLM
    -> verificador de proveniência numérica (regenera uma vez se houver órfão)
    -> gate de política
    -> sanitização de saída
    -> TurnResult + log
"""

from __future__ import annotations

from ..guardrails.policy import PolicyGate
from ..guardrails.verifier import NumericVerifier, extract_numbers
from ..llm.base import LLMClient, LLMResponse, Message
from ..schemas import (
    Insight,
    LLMUsage,
    ToolCallRecord,
    TurnResult,
    now_ms,
)
from ..security.injection import scan, wrap_untrusted
from ..security.sanitize import sanitize_input, sanitize_output
from ..tools.base import ToolError, ToolRegistry
from .context import RunContext

_BLOCK_MSG = (
    "Não consigo confirmar com segurança os números desta resposta a partir dos "
    "seus dados, então prefiro não arriscar uma informação incorreta. Pode "
    "reformular ou pedir que eu recalcule a partir das suas transações?"
)


class AgentHarness:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        *,
        system_prompt: str,
        seed: int = 42,
        max_steps: int = 6,
        abs_tol: float = 0.01,
        rel_tol: float = 0.005,
        regenerate_on_orphan: bool = True,
        allow_user_numbers: bool = True,
        policy: PolicyGate | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._system = system_prompt
        self._seed = seed
        self._max_steps = max_steps
        self._verifier = NumericVerifier(abs_tol=abs_tol, rel_tol=rel_tol)
        # PolicyGate injetavel: producao pluga a SuitabilityRule com catalogo;
        # default preserva o gate offline atual.
        self._policy = policy or PolicyGate()
        self._regen = regenerate_on_orphan
        self._allow_user_numbers = allow_user_numbers

    def run_turn(self, user_message: str) -> TurnResult:
        ctx = RunContext.new(self._seed)
        t0 = now_ms()

        clean = sanitize_input(user_message)
        injection_flags = scan(clean)
        ctx.logger.info(
            "turn_start", n_chars=len(clean), injection_flags=injection_flags, seed=self._seed
        )
        if injection_flags:
            ctx.logger.warning("injection_detected", flags=injection_flags)

        messages: list[Message] = [Message(role="user", content=clean)]
        insights: list[Insight] = []
        final_text = ""

        for _step in range(self._max_steps):
            resp = self._call_llm(ctx, messages)
            if not resp.wants_tools:
                final_text = resp.text
                break
            # cada resultado volta empacotado como dado não-confiável
            for call in resp.tool_calls:
                insight = self._run_tool(ctx, call.name, call.args)
                insights.append(insight)
                messages.append(
                    Message(
                        role="tool",
                        tool_call_id=call.id,
                        content=wrap_untrusted(insight.model_dump_json(), source=call.name),
                    )
                )
        else:
            ctx.logger.warning("max_steps_reached", steps=self._max_steps)
            final_text = final_text or ""

        return self._finalize(ctx, clean, final_text, insights, injection_flags, t0)

    def _call_llm(self, ctx: RunContext, messages: list[Message]) -> LLMResponse:
        t = now_ms()
        resp = self._llm.complete(messages, system=self._system, tools=self._tools.specs())
        latency = now_ms() - t
        from config.settings import get_settings  # import tardio evita ciclo

        s = get_settings()
        usage = LLMUsage(
            model=resp.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            latency_ms=round(latency, 1),
            cost_usd=s.cost_usd(resp.input_tokens, resp.output_tokens),
        )
        ctx.record_usage(usage)
        ctx.logger.info(
            "llm_call",
            model=usage.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            latency_ms=usage.latency_ms,
            cost_usd=usage.cost_usd,
            tool_calls=[c.name for c in resp.tool_calls],
        )
        return resp

    def _run_tool(self, ctx: RunContext, name: str, args: dict) -> Insight:  # noqa: ANN001
        t = now_ms()
        try:
            insight = self._tools.execute(name, args)
            ctx.record_tool(ToolCallRecord(name=name, ok=True, latency_ms=round(now_ms() - t, 1)))
            ctx.logger.info("tool_ok", tool=name, numeros=insight.numeros)
            return insight
        except ToolError as exc:
            ctx.record_tool(
                ToolCallRecord(
                    name=name, ok=False, latency_ms=round(now_ms() - t, 1), error=str(exc)
                )
            )
            ctx.logger.error("tool_error", tool=name, error=str(exc))
            # falha vira insight sem números, para o LLM não receber valor falso
            return Insight(fonte=name, resumo=f"Ferramenta '{name}' falhou.", numeros=[])

    def _finalize(self, ctx, user_msg, text, insights, injection_flags, t0) -> TurnResult:  # noqa: ANN001
        user_numbers = (
            [v for _, v in extract_numbers(user_msg)] if self._allow_user_numbers else []
        )
        report = self._verifier.check(text, insights, user_numbers=user_numbers)

        # uma tentativa de regeneração se houver número órfão
        if not report.ok and self._regen:
            ctx.logger.warning("orphan_numbers", orphans=report.orphans)
            # Reapresenta os fatos JÁ calculados pelas ferramentas para o modelo
            # reescrever grounded (sem isso, a regeneração ficava sem contexto e
            # tendia a devolver resposta vazia).
            fatos = "\n".join(f"- {ins.resumo}" for ins in insights if ins.resumo) or "(nenhum)"
            corrective = Message(
                role="user",
                content=(
                    "Sua resposta anterior continha números sem origem nas "
                    f"ferramentas: {report.orphans}. Reescreva a resposta final ao "
                    "cliente usando SOMENTE os fatos abaixo, reproduzindo os valores "
                    "exatamente como aparecem; não acrescente outros números, datas "
                    "ou contagens. Se algo não estiver nos fatos, não afirme.\n\n"
                    f"FATOS DAS FERRAMENTAS:\n{fatos}"
                ),
            )
            resp = self._call_llm(ctx, [Message(role="user", content=user_msg), corrective])
            text = resp.text
            report = self._verifier.check(text, insights, user_numbers=user_numbers)

        blocked = False
        block_reason = None
        if not report.ok:
            blocked, block_reason, text = True, "numeros_orfaos", _BLOCK_MSG
            ctx.logger.error("blocked", reason=block_reason, orphans=report.orphans)

        allowed_products = [r for ins in insights for r in ins.referencias]
        policy = self._policy.check(text, allowed_products=allowed_products)
        if not policy.ok:
            blocked, block_reason, text = True, "policy_violation", _BLOCK_MSG
            ctx.logger.error(
                "blocked", reason=block_reason, violations=[v.rule for v in policy.violations]
            )

        safe = sanitize_output(text)
        total_latency = round(now_ms() - t0, 1)
        ctx.logger.info(
            "turn_complete",
            blocked=blocked,
            block_reason=block_reason,
            verification_ok=report.ok,
            policy_ok=policy.ok,
            latency_ms=total_latency,
            total_cost_usd=round(sum(u.cost_usd for u in ctx.usage), 6),
            total_tokens=sum(u.input_tokens + u.output_tokens for u in ctx.usage),
        )
        return TurnResult(
            trace_id=ctx.trace_id,
            response=safe,
            blocked=blocked,
            block_reason=block_reason,
            verification=report,
            policy=policy,
            usage=ctx.usage,
            tool_calls=ctx.tool_calls,
            latency_ms=total_latency,
            injection_flags=injection_flags,
        )
