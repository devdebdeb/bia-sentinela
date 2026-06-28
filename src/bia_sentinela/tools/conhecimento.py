"""Ferramentas de base de conhecimento (escopo: lookup, sem RAG vetorial).

Duas consultas deterministicas sobre conteudo curado/inerte:
- consultar_glossario: define termos financeiros (glossario estatico).
- consultar_produto: detalha um produto do catalogo do cliente.

O conteudo e dado inerte: o harness ja o empacota como nao-confiavel antes de ir
ao modelo. Evolucao possivel para RAG por embeddings esta documentada em
docs/02 (referencia: SantanderAI/linear-adapter-trainer).
"""

from __future__ import annotations

import unicodedata

from pydantic import BaseModel, Field

from ..schemas import Insight, ProdutoFinanceiro


def _normaliza(texto: str) -> str:
    """Minusculas sem acento, para casar consultas de forma robusta."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c)).strip()


class ConsultarGlossarioInput(BaseModel):
    termo: str = Field(description="termo financeiro a definir (ex.: 'liquidez', 'CDB')")


class ConsultarGlossarioTool:
    name = "consultar_glossario"
    description = (
        "Define um termo financeiro a partir de um glossario curado (ex.: CDB, "
        "liquidez, suitability, reserva de emergencia). Use quando o cliente "
        "perguntar 'o que e' ou pedir o significado de um conceito."
    )
    input_model = ConsultarGlossarioInput

    def __init__(self, glossario: dict[str, str]) -> None:
        # Indice normalizado -> (termo_original, definicao) para casar sem acento.
        self._idx = {_normaliza(t): (t, d) for t, d in glossario.items()}

    def run(self, args: ConsultarGlossarioInput) -> Insight:
        consulta = _normaliza(args.termo)
        achado: tuple[str, str] | None = self._idx.get(consulta)
        if achado is None:
            # casamento por continencia (consulta contida no termo ou vice-versa)
            for chave, par in self._idx.items():
                if consulta and (consulta in chave or chave in consulta):
                    achado = par
                    break
        if achado is None:
            return Insight(
                fonte=self.name,
                resumo=f"Nao tenho '{args.termo}' no glossario.",
                numeros=[],
                referencias=[],
                dados={"encontrado": False, "termo": args.termo},
            )
        termo, definicao = achado
        return Insight(
            fonte=self.name,
            resumo=f"{termo}: {definicao}",
            numeros=[],
            referencias=[f"glossario:{termo}"],
            dados={"encontrado": True, "termo": termo, "definicao": definicao},
        )


class ConsultarProdutoInput(BaseModel):
    consulta: str = Field(description="produto_id ou nome do produto a detalhar")


class ConsultarProdutoTool:
    name = "consultar_produto"
    description = (
        "Detalha um produto do catalogo (classe, risco, rentabilidade, liquidez, "
        "aplicacao minima) por id ou nome. Use quando o cliente perguntar sobre um "
        "produto especifico. Nao recomenda; apenas descreve."
    )
    input_model = ConsultarProdutoInput

    def __init__(self, produtos: list[ProdutoFinanceiro]) -> None:
        self._produtos = produtos

    def _buscar(self, consulta: str) -> ProdutoFinanceiro | None:
        alvo = _normaliza(consulta)
        for p in self._produtos:
            if _normaliza(p.produto_id) == alvo or _normaliza(p.nome) == alvo:
                return p
        for p in self._produtos:  # fallback: continencia no nome
            if alvo and alvo in _normaliza(p.nome):
                return p
        return None

    def run(self, args: ConsultarProdutoInput) -> Insight:
        p = self._buscar(args.consulta)
        if p is None:
            return Insight(
                fonte=self.name,
                resumo=f"Nao encontrei o produto '{args.consulta}' no catalogo.",
                numeros=[],
                referencias=[],
                dados={"encontrado": False, "consulta": args.consulta},
            )
        numeros: list[float] = []
        partes = [f"{p.nome} ({p.classe}, risco minimo {p.risco})"]
        if p.rentabilidade_aa is not None:
            numeros.append(float(p.rentabilidade_aa))
            partes.append(f"rentabilidade {p.rentabilidade_aa:.1f}% a.a.")
        elif p.rentabilidade_desc:
            # Texto relativo (ex.: "100% da Selic"); numeros vao para a
            # proveniencia via o resumo (collect_allowed extrai do resumo).
            partes.append(f"rentabilidade {p.rentabilidade_desc}")
        if p.liquidez:
            partes.append(f"liquidez {p.liquidez}")
        if p.aplicacao_minima is not None:
            numeros.append(float(p.aplicacao_minima))
            partes.append(f"aplicacao minima R$ {p.aplicacao_minima:.2f}")
        return Insight(
            fonte=self.name,
            resumo=". ".join(partes) + ".",
            numeros=numeros,
            referencias=[p.produto_id],
            dados={"encontrado": True, **p.model_dump()},
        )
