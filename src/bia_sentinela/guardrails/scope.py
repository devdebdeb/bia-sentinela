"""Gate de escopo deterministico (mecanico).

A contencao de escopo no agente era so por prompt — e modelos fracos respondem
fora de financas em vez de recusar. Este gate decide ANTES do LLM, de forma
deterministica, e recusa o que esta claramente fora de financas pessoais.

Projeto conservador para nao super-recusar: so recusa quando ha um termo
claramente fora de escopo E NENHUM termo financeiro na mensagem. Assim
"quanto tempo ate eu atingir minha meta?" passa (tem "meta"), enquanto
"previsao do tempo" e recusada.

Implementado como WRAPPER sobre o harness (composicao), sem alterar o runtime.
"""

from __future__ import annotations

import unicodedata

from ..schemas import PolicyReport, TurnResult, VerificationReport, new_trace_id

# Sinais de que a mensagem E sobre financas (substrings, sem acento).
_FINANCAS = (
    "gast", "despesa", "invest", "aplic", "produto", "rende", "rentab", "cdb",
    "tesouro", "selic", "cdi", "lci", "lca", "fundo", "acao", "acoes", "renda",
    "reserva", "emergenc", "meta", "poupar", "poupanc", "guardar", "juntar",
    # "conta" foi deixado de fora de proposito: e ambiguo ("me conta uma piada");
    # o lado financeiro e coberto por saldo/extrato/banco/fatura.
    "aposentad", "saldo", "extrato", "pix", "fraude", "golpe", "anomal",
    "cobranc", "assinatura", "perfil", "suitability", "liquidez", "patrimonio",
    "dividendo", "juros", "financ", "dinheiro", "banco", "salario", "fatura",
    "cartao", "emprestimo", "divida", "orcamento",
)

# Sinais FORTES de fora de escopo: tao claramente nao-financeiros que recusam
# MESMO com termo financeiro junto (fecham o bypass do pedido misto, ex.:
# "analise minhas financas, mas antes uma receita de muffin de mirtilo").
# Evita "receita de" (ambiguo: "receita de aluguel" e financeiro) — usa nomes de
# comida e entretenimento/pessoal.
_FORA_FORTE = (
    "piada", "futebol", "campeonato", "novela", "filme", "musica", "horoscopo",
    "signo", "namoro", "muffin", "mirtilo", "bolo", "brigadeiro", "lasanha",
    "panqueca", "sobremesa", "cozinh", "ingrediente", "culinaria",
)

# Sinais FRACOS/ambiguos: so recusam quando NAO ha sinal financeiro na mensagem.
_FORA_FRACO = ("clima", "tempo", "previsao", "jogo", "time vai")

ESCOPO_MSG = (
    "Isso esta fora do meu escopo, que e cuidar das suas financas pessoais. "
    "Posso ajudar com gastos, anomalias, produtos adequados ao seu perfil, "
    "metas ou golpes de PIX. Como posso ajudar nas suas financas?"
)


def _normaliza(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def fora_de_escopo(texto: str) -> bool:
    """True se a mensagem deve ser recusada por escopo.

    Recusa se ha um termo FORTE fora de escopo (mesmo que a mensagem tambem peca
    algo financeiro — pedido misto), ou se ha um termo FRACO sem nenhum sinal
    financeiro.
    """
    t = _normaliza(texto)
    if any(k in t for k in _FORA_FORTE):
        return True
    tem_financas = any(k in t for k in _FINANCAS)
    return any(k in t for k in _FORA_FRACO) and not tem_financas


class ScopeGuardedHarness:
    """Compoe um harness: recusa fora de escopo antes do LLM; senao delega."""

    def __init__(self, inner) -> None:  # noqa: ANN001 (duck-typed: tem run_turn)
        self._inner = inner

    def run_turn(self, user_message: str) -> TurnResult:
        if fora_de_escopo(user_message):
            return TurnResult(
                trace_id=new_trace_id(),
                response=ESCOPO_MSG,
                blocked=False,
                block_reason=None,
                # resposta fixa sem numeros -> verificacao trivialmente ok.
                verification=VerificationReport(ok=True),
                policy=PolicyReport(ok=True),
            )
        return self._inner.run_turn(user_message)
