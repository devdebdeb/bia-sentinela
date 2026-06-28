"""Análise exploratória e visualizações.

Roda o pipeline de dados ponta a ponta e produz:
  - analysis/figures/*.png
  - analysis/eda_report.json

Uso: PYTHONPATH=src:. python analysis/eda.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bia_sentinela.data import features as F  # noqa: E402
from bia_sentinela.data.ingestion import (  # noqa: E402
    carregar_perfil_raw,
    carregar_transacoes,
)
from bia_sentinela.data.profiling import perfil_qualidade  # noqa: E402

RAW = Path("data/raw")
FIG = Path("analysis/figures")
FIG.mkdir(parents=True, exist_ok=True)

# Paleta consistente entre figuras.
AZUL, VERDE, VERMELHO, CINZA = "#1f4e79", "#2e8b57", "#c0392b", "#95a5a6"
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.25, "font.size": 10,
                     "text.parse_math": False})


def _fig_fluxo(fm) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.2))
    x = range(len(fm))
    ax.bar([i - 0.2 for i in x], fm["entradas"], width=0.4, label="Entradas", color=VERDE)
    ax.bar([i + 0.2 for i in x], fm["saidas"], width=0.4, label="Saídas", color=VERMELHO)
    ax.plot(list(x), fm["poupanca"], color=AZUL, marker="o", lw=2, label="Poupança")
    ax.set_xticks(list(x))
    ax.set_xticklabels(fm["mes"], rotation=45, ha="right")
    ax.set_title("Fluxo de caixa mensal: o mês que destoa conta uma história")
    ax.set_ylabel("R$")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "01_fluxo_caixa.png")
    plt.close(fig)


def _fig_categorias(cat) -> None:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.barh(cat["categoria"][::-1], cat["total"][::-1], color=AZUL)
    for i, (t, s) in enumerate(zip(cat["total"][::-1], cat["share"][::-1])):
        ax.text(t, i, f"  {s:.0%}", va="center", fontsize=8, color=CINZA)
    ax.set_title("Para onde vai o dinheiro: composição de gastos (12 meses)")
    ax.set_xlabel("R$ acumulado")
    fig.tight_layout()
    fig.savefig(FIG / "02_gastos_categoria.png")
    plt.close(fig)


def _fig_assinatura(df, descricao: str) -> None:
    sub = df[df["descricao"] == descricao].copy()
    serie = sub.groupby("mes")["valor"].sum().abs().sort_index()
    fig, ax = plt.subplots(figsize=(9, 4.0))
    ax.plot(range(len(serie)), serie.values, marker="o", color=AZUL, lw=2)
    salto = int(serie.values.argmax())
    ax.scatter([salto], [serie.values[salto]], color=VERMELHO, zorder=5, s=80)
    ax.annotate(
        f"salto: R$ {serie.values[0]:.2f} -> R$ {serie.values[salto]:.2f}",
        (salto, serie.values[salto]), textcoords="offset points", xytext=(-150, -10),
        color=VERMELHO, fontsize=9, arrowprops=dict(arrowstyle="->", color=VERMELHO),
    )
    ax.set_xticks(range(len(serie)))
    ax.set_xticklabels(serie.index, rotation=45, ha="right")
    ax.set_title(f"Assinatura recorrente que dobrou: '{descricao}'")
    ax.set_ylabel("R$/mês")
    fig.tight_layout()
    fig.savefig(FIG / "03_assinatura_anomalia.png")
    plt.close(fig)


def _fig_caixa(co) -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    labels = ["Reserva\nrecomendada", "Caixa\nocioso"]
    vals = [co["reserva_recomendada"], co["caixa_ocioso"]]
    ax.bar(labels, vals, color=[CINZA, VERDE])
    for i, v in enumerate(vals):
        ax.text(i, v, f"R$ {v:,.0f}", ha="center", va="bottom", fontsize=10)
    ax.set_title("Caixa ocioso = oportunidade que o agente antecipa")
    ax.set_ylabel("R$")
    fig.tight_layout()
    fig.savefig(FIG / "04_caixa_ocioso.png")
    plt.close(fig)


def main() -> dict:
    df = carregar_transacoes(RAW / "transacoes.csv")
    perfil = carregar_perfil_raw(RAW / "perfil_investidor.json")

    qualidade = perfil_qualidade(df)
    fm = F.media_movel_gastos(df)
    cat = F.gasto_por_categoria(df)
    rec = F.cobrancas_recorrentes(df)
    co = F.caixa_ocioso(perfil["saldo_conta"], fm)

    _fig_fluxo(fm)
    _fig_categorias(cat)
    desc_sub = rec.iloc[0]["descricao"] if len(rec) else "Streaming Premium (assinatura)"
    _fig_assinatura(df, desc_sub)
    _fig_caixa(co)

    mes_pico = fm.loc[fm["desvio_vs_mm"].idxmax()]
    report = {
        "qualidade": qualidade,
        "taxa_poupanca_media": round(float(fm["taxa_poupanca"].mean()), 4),
        "mes_maior_desvio": {"mes": mes_pico["mes"], "desvio_vs_media_movel": float(mes_pico["desvio_vs_mm"])},
        "top_categoria": {"categoria": cat.iloc[0]["categoria"], "share": float(cat.iloc[0]["share"])},
        "assinatura_recorrente": rec.iloc[0].to_dict() if len(rec) else {},
        "caixa_ocioso": co,
        "figuras": sorted(p.name for p in FIG.glob("*.png")),
    }
    Path("analysis/eda_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
