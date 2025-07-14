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

# ---------- CLI ----------
p = argparse.ArgumentParser(description="Plota métricas de arquivos .vec/.sca do gPTP")
p.add_argument("--results", type=Path, default=Path("results"))
p.add_argument("--metric", action="append", required=True,
               help="Nome ou regex da métrica (ex.: offsetFromGm, rateRatio.*)")
p.add_argument("--outdir", type=Path, default=Path("figs"))
p.add_argument("--max-runs", type=int, default=None)
args = p.parse_args()
args.outdir.mkdir(parents=True, exist_ok=True)

# ---------- Parser robusto para .vec ----------
def parse_vec(file: Path) -> pd.DataFrame:
    """
    Lê .vec do OMNeT++ 6 — cabeçalho: sem aspas; dados: <id> <ev> <t> <val>
    Retorna DataFrame com colunas: time, value, run, module, metric
    """
    id_meta = {}                 # id -> dict(module, metric, run)
    rows = []
    run = file.stem

    with file.open() as f:
        for line in f:
            if line.startswith("vector"):          # cabeçalho
                # vector 12 modulo caminho metrica ETV
                parts = line.split()
                if len(parts) >= 4:
                    vec_id, module, metric = parts[1:4]
                    id_meta[vec_id] = {"module": module,
                                        "metric": metric,
                                        "run": run}
            elif line and line[0].isdigit():       # linha de dados
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

# ---------- Carrega todos os .vec ----------
vec_files = sorted(args.results.glob("*.vec"))
if args.max_runs:
    vec_files = vec_files[:args.max_runs]

print("⏳ Lendo arquivos .vec…")
df_all = pd.concat(
    (parse_vec(f) for f in tqdm(vec_files, unit="run", ncols=80)),
    ignore_index=True
)

if df_all.empty:
    raise SystemExit("Nenhum dado válido encontrado nos .vec - verifique formato ou caminho.")

# ---------- Filtra métricas desejadas ----------
patterns = [re.compile(expr, re.I) for expr in args.metric]
sel = df_all["metric"].apply(lambda m: any(p.search(m) for p in patterns))
df = df_all[sel]

if df.empty:
    raise SystemExit(f"Nenhuma amostra bateu com: {args.metric}")

# ---------- Gera gráficos ----------
print("📈 Gerando gráficos…")
for (run, metric), grp in df.groupby(["run", "metric"]):
    fig, ax = plt.subplots()
    for module, sub in grp.groupby("module"):
        sub.plot(x="time", y="value", ax=ax, label=module)

    ax.set_title(f"{metric} — {run}")
    ax.set_xlabel("Tempo [s]")
    ax.set_ylabel(metric)
    ax.grid(alpha=.3)
    ax.legend(fontsize="small")
    fig.tight_layout()
    fname = args.outdir / f"{run}_{metric.replace(':','_')}.png"
    fig.savefig(fname, dpi=150)
    plt.close(fig)
    print(f"  ✔ {fname}")

print("\n✅ Concluído! Veja os PNGs em", args.outdir)
