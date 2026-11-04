#!/usr/bin/env python3
"""Build the AutoControl H0-vs-SafeHarness comparison report.

Reads the paired episode dumps and Monitor JSONL files, then reports:
  * oracle realized-harm and utility rates by risk category and S/T;
  * Monitor action-risk rates by the same slices;
  * paired transitions (harm -> no harm, no harm -> harm, etc.);
  * SafeHarness intervention counts.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CATEGORY = {
    "cm": "Capability Misuse",
    "cw": "Covert Whistleblowing",
    "ea": "Evaluation Awareness",
    "ic": "Instrumental Convergence",
    "oe": "Oversight Evasion",
    "sg": "Specification Gaming",
    "sm": "Strategic Misalignment",
}


def load_episodes(path: Path) -> dict:
    result = {}
    with gzip.open(path, "rt") as handle:
        for line in handle:
            row = json.loads(line)
            result[row["cell"]] = row
    return result


def load_monitor(path: Path) -> dict:
    result = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            result[row["cell"]] = row
    return result


def split_cell(cell: str) -> tuple[str, str, str]:
    task, _, seed = cell.partition("#")
    uid, _, level = task.rpartition("@")
    prefix = uid.split(":")[-1].split("_")[0]
    return CATEGORY.get(prefix, prefix), level or "NA", seed


def rate(n: int, d: int) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def summarize(arm: str, episodes: dict, monitor: dict) -> dict:
    slices = collections.defaultdict(lambda: {
        "n": 0, "harm": 0, "utility": 0, "monitor_n": 0, "monitor_risky": 0,
    })
    for cell, ep in episodes.items():
        cat, level, _ = split_cell(cell)
        for key in (("ALL", "ALL"), (cat, "ALL"), ("ALL", level), (cat, level)):
            row = slices[key]
            row["n"] += 1
            row["harm"] += int(bool((ep.get("outcome") or {}).get("harm")))
            row["utility"] += int(bool((ep.get("outcome") or {}).get("utility")))
            mon = monitor.get(cell) or {}
            if mon.get("parse_ok"):
                row["monitor_n"] += 1
                row["monitor_risky"] += int(bool(mon.get("is_risky")))
    return {
        "arm": arm,
        "slices": {
            "|".join(key): {
                **row,
                "harm_pct": rate(row["harm"], row["n"]),
                "utility_pct": rate(row["utility"], row["n"]),
                "monitor_pct": rate(row["monitor_risky"], row["monitor_n"]),
            }
            for key, row in sorted(slices.items())
        },
    }


def paired_transitions(h0: dict, sh: dict, h0m: dict, shm: dict) -> dict:
    oracle = collections.Counter()
    monitor = collections.Counter()
    utility = collections.Counter()
    for cell in sorted(set(h0) & set(sh)):
        a = bool((h0[cell].get("outcome") or {}).get("harm"))
        b = bool((sh[cell].get("outcome") or {}).get("harm"))
        oracle[("harm->harm" if a and b else
                "harm->no_harm" if a and not b else
                "no_harm->harm" if not a and b else "no_harm->no_harm")] += 1
        ua = bool((h0[cell].get("outcome") or {}).get("utility"))
        ub = bool((sh[cell].get("outcome") or {}).get("utility"))
        utility[("utility->utility" if ua and ub else
                 "utility->no_utility" if ua and not ub else
                 "no_utility->utility" if not ua and ub else "no_utility->no_utility")] += 1
        ma = (h0m.get(cell) or {}).get("is_risky")
        mb = (shm.get(cell) or {}).get("is_risky")
        if ma is not None and mb is not None:
            monitor[("risky->risky" if ma and mb else
                     "risky->safe" if ma and not mb else
                     "safe->risky" if not ma and mb else "safe->safe")] += 1
    return {"oracle": dict(oracle), "utility": dict(utility), "monitor": dict(monitor)}


def interventions(episodes: dict) -> dict:
    tools = collections.Counter()
    reasons = collections.Counter()
    total = 0
    for ep in episodes.values():
        for item in ep.get("interventions") or []:
            total += 1
            tools[item.get("tool") or "?"] += 1
            reasons[(item.get("check") or "?", str(item.get("reason") or "")[:100])] += 1
    return {
        "total": total,
        "tools": dict(tools.most_common(20)),
        "reasons": [{"check": k[0], "reason": k[1], "n": v}
                    for k, v in reasons.most_common(20)],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h0-eps", required=True)
    parser.add_argument("--h0-monitor", required=True)
    parser.add_argument("--sh-eps", required=True)
    parser.add_argument("--sh-monitor", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    h0 = load_episodes(Path(args.h0_eps))
    sh = load_episodes(Path(args.sh_eps))
    h0m = load_monitor(Path(args.h0_monitor))
    shm = load_monitor(Path(args.sh_monitor))
    report = {
        "h0": summarize("H0", h0, h0m),
        "safeharness": summarize("SafeHarness", sh, shm),
        "paired": paired_transitions(h0, sh, h0m, shm),
        "interventions": interventions(sh),
    }

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# AutoControl BARE vs SafeHarness",
        "",
        "## Overall",
        "",
        "| Arm | n | Monitor risky (primary) | TaskSpec rule hit (secondary) | TaskSpec utility |",
        "|---|---:|---:|---:|---:|",
    ]
    for key, label in (("h0", "BARE"), ("safeharness", "SafeHarness")):
        row = report[key]["slices"]["ALL|ALL"]
        lines.append(
            f"| {label} | {row['n']} | {row['monitor_pct']}% | "
            f"{row['harm_pct']}% | {row['utility_pct']}% |")
    lines += ["", "## By risk category", "",
              "| Arm | Category | n | Monitor risky | TaskSpec rule hit | TaskSpec utility |",
              "|---|---|---:|---:|---:|---:|"]
    for key, label in (("h0", "BARE"), ("safeharness", "SafeHarness")):
        for slice_key, row in report[key]["slices"].items():
            if not slice_key.endswith("|ALL") or slice_key == "ALL|ALL":
                continue
            lines.append(
                f"| {label} | {slice_key.split('|')[0]} | {row['n']} | "
                f"{row['monitor_pct']}% | {row['harm_pct']}% | {row['utility_pct']}% |")
    lines += ["", "## By elicitation level", "",
              "| Arm | S/T | n | Monitor risky | TaskSpec rule hit | TaskSpec utility |",
              "|---|---|---:|---:|---:|---:|"]
    for key, label in (("h0", "BARE"), ("safeharness", "SafeHarness")):
        for slice_key, row in report[key]["slices"].items():
            if not slice_key.startswith("ALL|") or slice_key == "ALL|ALL":
                continue
            lines.append(
                f"| {label} | {slice_key.split('|')[1]} | {row['n']} | "
                f"{row['monitor_pct']}% | {row['harm_pct']}% | {row['utility_pct']}% |")
    lines += ["", "## Paired transitions (oracle = TaskSpec rule only)", "", "```json",
              json.dumps(report["paired"], ensure_ascii=False, indent=2), "```",
              "", "## SafeHarness interventions", "", "```json",
              json.dumps(report["interventions"], ensure_ascii=False, indent=2), "```"]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print((out / "report.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
