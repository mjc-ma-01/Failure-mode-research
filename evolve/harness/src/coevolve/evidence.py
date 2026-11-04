"""证据包：给提案者的输入（每来源配额 + 四条桶 + N/A + 最差案例）。"""
from __future__ import annotations

import collections


def build(report, edits, classified: dict, per_source_quota: int = 3,
          current_library: dict | None = None) -> dict:
    pkg: dict = {
        "criterion": classified.get("criterion"),
        "sources": {},
        "current_library": current_library or {},
        "instruction": "优先针对 Δ抵抗/未测到 桶里最大的那类提编辑；不要重复已有机制类别。",
    }
    for src, rec in classified["per_source"].items():
        cells = rec["cells"]
        worst = [(c, v["vector"], {"harm": v["base_harm"], "utility": v["base_utility"]})
                 for c, v in cells.items() if v["bucket"] in ("Δ抵抗", "未测到", "Δ自伤")]
        pkg["sources"][src] = {
            "n_cells": len(cells),
            "buckets": {k: v for k, v in rec["buckets"].items()},
            "na_counts": dict(rec["na"]),
            "worst_cases": worst[:per_source_quota],
        }
    return pkg
