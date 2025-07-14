#!/usr/bin/env python3
"""
plot_gptp.py — converte resultados do showcase gPTP (INET/OMNeT++)
              em DataFrames e gera gráficos.
Compatível com OMNeT++ 6 (cabecalhos sem aspas + linhas de 4 campos).
"""

import argparse, re
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from tqdm import tqdm

# -------------------------------------------------------------------
# 1. Argumentos de linha de comando
# -------------------------------------------------------------------
cli = argparse.ArgumentParser(description="Plota métricas de arquivos .vec/.sca do gPTP")
cli.add_argument("--results", type=Path, default=Path("results"),
                 help="Diretório com arquivos .vec/.sca")
cli.add_argument("--metric", action="append", required=True,
                 help="Nome ou regex da métrica (ex.: offsetFromGm, rateRatio.*)")
cli.add_argument("--outdir", type=Path, default=Path("figs"),
                 help="Onde salvar as figuras")
cli.add_argument("--max-runs", type=int, default=None,
                 help="Limita quantos .vec processar (debug)")
args = cli.parse_args()
args.outdir.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------------
# 2. Função para parsear .vec (formato OMNeT++ 6)
# -------------------------------------------------------------------
def parse_vec(file: Path) -> pd.DataFrame:
    """
    Converte um .vec (cabecalho: 'vector id módulo métrica ETV'; linhas: 'id ev t val')
    em DataFrame com colunas: time, value, run, module, metric
    """
    id_meta, rows = {}, []
    run_name = file.stem

    with file.open() as f:
        for line in f:
            if line.startswith("vector"):
                parts = line.split()
                if len(parts) >= 4:
                    vec_id, module, metric = parts[1:4]
                    id_meta[vec_id] = {"module": module,
                                       "metric": metric,
                                       "run": run_name}
            elif line and line[0].isdigit():
                parts = line.split()
                if len(parts) >= 4:
                    vec_id, _, sim_time, value = parts[:4]
                    meta = id_meta.get(vec_id)
                    if meta:
                        rows.append({
                            "time":  float(sim_time),
                            "value": float(value),
                            **meta
                        })
    return pd.DataFrame(rows)

# -------------------------------------------------------------------
# 3. Carrega todos os .vec
# -------------------------------------------------------------------
vec_files = sorted(args.results.glob("*.vec"))
if args.max_runs:
    vec_files = vec_files[:args.max_runs]

print("⏳ Lendo arquivos .vec…")
df_all = pd.concat((parse_vec(f) for f in tqdm(vec_files, unit="run", ncols=80)),
                   ignore_index=True)

if df_all.empty:
    raise SystemExit("Nenhum dado válido encontrado nos .vec — verifique formato/caminho.")

# -------------------------------------------------------------------
# 4. Filtra métricas desejadas
# -------------------------------------------------------------------
patterns = [re.compile(expr, re.I) for expr in args.metric]
mask = df_all["metric"].apply(lambda m: any(p.search(m) for p in patterns))
df = df_all[mask]

if df.empty:
    raise SystemExit(f"Nenhuma amostra bateu com as expressões: {args.metric}")

# -------------------------------------------------------------------
# 5. Gera gráficos
# -------------------------------------------------------------------
print("📈 Gerando gráficos…")
for (run, metric), grp in df.groupby(["run", "metric"]):
    # figura ligeiramente mais larga para acomodar legenda
    fig, ax = plt.subplots(figsize=(8, 4.5))

    # plota cada módulo
    for module, sub in grp.groupby("module"):
        sub.plot(x="time", y="value", ax=ax, label=module)

    # ajustes de layout
    ax.set_title(f"{metric} — {run}")
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel(metric)
    ax.grid(alpha=.3)

    # ------------------ legenda fora do gráfico ------------------
    handles, labels = ax.get_legend_handles_labels()
    if len(labels) > 0:
        ax.legend(handles, labels,
                  fontsize="small",
                  bbox_to_anchor=(1.02, 1),  # canto superior direito, fora do eixo
                  loc="upper left",
                  borderaxespad=0.)
    # -------------------------------------------------------------

    fig.tight_layout()
    fname = args.outdir / f"{run}_{metric.replace(':','_')}.png"
    fig.savefig(fname, dpi=150, bbox_inches="tight")  # garante que a legenda caiba
    plt.close(fig)
    print(f"  ✔ {fname}")

print("\n✅ Concluído! Veja os PNGs em", args.outdir.resolve())
