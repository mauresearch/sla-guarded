"""Aggregate a raw Azure LLM inference trace into 30 s bins.

The aggregated files used in the evaluation are already provided in
data/azure_llm_traces/, so this step is only needed to rebuild them from the
original traces (see the README for download links).

Usage:
  python experiments/08_trace_prepare.py AzureLLMInferenceTrace_conv_1week.csv conv_1week
  python experiments/08_trace_prepare.py AzureLLMInferenceTrace_code_1week.csv code_1week
  python experiments/08_trace_prepare.py AzureLLMInferenceTrace_conv.csv conv
  python experiments/08_trace_prepare.py AzureLLMInferenceTrace_code.csv code

Output columns: bin (30 s index from midnight of the first day), requests,
gen_tokens, ctx_tokens, t0 (midnight of the first day).
"""

import sys

import numpy as np
import pandas as pd

from common import DATA

BIN_S = 30

if __name__ == "__main__":
    src, name = sys.argv[1], sys.argv[2]
    acc = {}
    t0 = None
    n = 0
    for chunk in pd.read_csv(
        src, chunksize=2_000_000, usecols=["TIMESTAMP", "ContextTokens", "GeneratedTokens"]
    ):
        ts = pd.to_datetime(chunk["TIMESTAMP"], format="mixed")
        if t0 is None:
            t0 = ts.min().floor("D")
        b = ((ts - t0).dt.total_seconds() // BIN_S).astype(np.int64)
        g = (
            pd.DataFrame({"b": b, "g": chunk["GeneratedTokens"], "c": chunk["ContextTokens"]})
            .groupby("b")
            .agg(n=("g", "size"), g=("g", "sum"), c=("c", "sum"))
        )
        for k, row in g.iterrows():
            cnt, gen, ctx = acc.get(k, (0, 0, 0))
            acc[k] = (cnt + row.n, gen + row.g, ctx + row.c)
        n += len(chunk)
    keys = sorted(acc)
    out = pd.DataFrame(
        {
            "bin": keys,
            "requests": [acc[k][0] for k in keys],
            "gen_tokens": [acc[k][1] for k in keys],
            "ctx_tokens": [acc[k][2] for k in keys],
        }
    )
    out["t0"] = str(t0)
    DATA.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA / f"{name}.csv", index=False)
    span_h = (out.bin.max() - out.bin.min() + 1) * BIN_S / 3600
    print(
        f"{src}: {n} requests, start {t0}, {len(out)} bins, span {span_h:.1f} h, "
        f"mean {n / (span_h * 3600):.1f} req/s, mean response {out.gen_tokens.sum() / n:.0f} tokens"
    )
