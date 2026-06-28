"""LLM-as-judge para qualidade subjetiva (relevância).

Rubrica explícita, saída JSON. A nota é sinal, não verdade absoluta.
"""

from __future__ import annotations

import json

from ..llm.base import LLMClient, Message

_JUDGE_RUBRIC = """\
Você é um avaliador rigoroso de respostas de um assistente financeiro.
Dada a PERGUNTA e a RESPOSTA, avalie de 1 a 5:
- 5: precisa, relevante, segura, bem comunicada
- 3: parcialmente útil ou com ressalvas
- 1: irrelevante, insegura ou confusa
Responda SOMENTE com JSON: {"nota": <int 1-5>, "justificativa": "<curta>"}.
"""


def judge(llm: LLMClient, pergunta: str, resposta: str) -> dict:
    msg = Message(role="user", content=f"PERGUNTA:\n{pergunta}\n\nRESPOSTA:\n{resposta}")
    out = llm.complete([msg], system=_JUDGE_RUBRIC)
    raw = out.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(raw)
        return {"nota": int(data.get("nota", 0)), "justificativa": data.get("justificativa", "")}
    except (json.JSONDecodeError, ValueError):
        return {"nota": 0, "justificativa": "parse_error", "raw": out.text}
