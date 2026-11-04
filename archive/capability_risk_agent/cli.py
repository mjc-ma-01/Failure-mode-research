from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from .blindspots import HARNESS_BLINDSPOTS, SEMANTIC_RISKS, blindspot_catalog_text, select_blindspot_keys
from .json_utils import read_records
from .pipeline import build_harness_gap_scenarios, build_scenarios
from .runtime import judge_trajectories, run_scenarios
from .taxonomy import CAPABILITY_GAPS, RISK_TYPES, select_keys, taxonomy_as_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="capability-risk-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_tax = sub.add_parser("show-taxonomy", help="Print capability gaps and risk types.")
    p_tax.add_argument(
        "--kind",
        choices=["all", "capabilities", "risks", "blindspots", "semantic-risks"],
        default="all",
    )

    p_gen = sub.add_parser("generate", help="Generate capability-risk scenarios.")
    p_gen.add_argument("--pipeline", choices=["harness-gap", "capability-gap"], default="harness-gap")
    p_gen.add_argument("--out", default="capability_risk_agent/out/scenarios.json")
    p_gen.add_argument("--blindspots", default="semantic_scope_drift,provenance_certification_gap,shallow_validator_overtrust")
    p_gen.add_argument("--semantic-risks", default="false_verification,wrong_entity_action,contextual_privacy_leak")
    p_gen.add_argument("--capabilities", default="state_tracking,uncertainty_calibration,tool_affordance")
    p_gen.add_argument("--risks", default="privacy_leakage,wrong_record_mutation,collateral_state_change")
    p_gen.add_argument("--n-per-cell", type=int, default=1)
    p_gen.add_argument("--model", default="gpt-4o-mini")
    p_gen.add_argument("--temperature", type=float, default=0.7)
    p_gen.add_argument("--dry-run", action="store_true")
    p_gen.add_argument("--keep-failed-qc", action="store_true")
    p_gen.add_argument("--keep-safeharness-blocked", action="store_true")
    p_gen.add_argument("--dedupe-threshold", type=float, default=0.88)
    p_gen.add_argument("--seed", type=int, default=7)

    p_run = sub.add_parser("run", help="Run a target LLM agent on generated scenarios.")
    p_run.add_argument("--scenarios", default="capability_risk_agent/out/scenarios.json")
    p_run.add_argument("--out", default="capability_risk_agent/out/trajectories.json")
    p_run.add_argument("--model", default="deepseek-v4-flash")
    p_run.add_argument("--temperature", type=float, default=0.2)
    p_run.add_argument("--max-steps", type=int, default=8)
    p_run.add_argument("--security-mode", choices=["none", "safeharness"], default="safeharness")

    p_judge = sub.add_parser("judge", help="Judge trajectories.")
    p_judge.add_argument("--scenarios", default="capability_risk_agent/out/scenarios.json")
    p_judge.add_argument("--trajectories", default="capability_risk_agent/out/trajectories.json")
    p_judge.add_argument("--out", default="capability_risk_agent/out/judgments.json")
    p_judge.add_argument("--model", default="gpt-4o-mini")
    p_judge.add_argument("--temperature", type=float, default=0.1)
    p_judge.add_argument("--heuristic", action="store_true")

    p_sum = sub.add_parser("summarize", help="Summarize a JSON or JSONL records file.")
    p_sum.add_argument("--input", default="capability_risk_agent/out/scenarios.json")
    p_sum.add_argument("--out", default="")

    args = parser.parse_args(argv)
    if args.command == "show-taxonomy":
        _show_taxonomy(args.kind)
        return 0
    if args.command == "generate":
        if args.pipeline == "harness-gap":
            blindspot_keys = select_blindspot_keys(args.blindspots, HARNESS_BLINDSPOTS, "harness blindspot")
            semantic_risk_keys = select_blindspot_keys(args.semantic_risks, SEMANTIC_RISKS, "semantic risk")
            scenarios = build_harness_gap_scenarios(
                blindspot_keys=blindspot_keys,
                semantic_risk_keys=semantic_risk_keys,
                n_per_cell=args.n_per_cell,
                out_path=Path(args.out),
                dry_run=args.dry_run,
                model=args.model,
                temperature=args.temperature,
                keep_failed_qc=args.keep_failed_qc,
                require_safeharness_pass=not args.keep_safeharness_blocked,
                dedupe_threshold=args.dedupe_threshold,
                seed=args.seed,
            )
        else:
            capability_keys = select_keys(args.capabilities, CAPABILITY_GAPS, "capability gap")
            risk_keys = select_keys(args.risks, RISK_TYPES, "risk type")
            scenarios = build_scenarios(
                capability_keys=capability_keys,
                risk_keys=risk_keys,
                n_per_cell=args.n_per_cell,
                out_path=Path(args.out),
                dry_run=args.dry_run,
                model=args.model,
                temperature=args.temperature,
                keep_failed_qc=args.keep_failed_qc,
                dedupe_threshold=args.dedupe_threshold,
                seed=args.seed,
            )
        print(f"Wrote {len(scenarios)} scenarios to {args.out}")
        return 0
    if args.command == "run":
        trajectories = run_scenarios(
            scenarios_path=Path(args.scenarios),
            out_path=Path(args.out),
            model=args.model,
            max_steps=args.max_steps,
            temperature=args.temperature,
            security_mode=args.security_mode,
        )
        print(f"Wrote {len(trajectories)} trajectories to {args.out}")
        return 0
    if args.command == "judge":
        judgments = judge_trajectories(
            scenarios_path=Path(args.scenarios),
            trajectories_path=Path(args.trajectories),
            out_path=Path(args.out),
            model=args.model,
            heuristic=args.heuristic,
            temperature=args.temperature,
        )
        print(f"Wrote {len(judgments)} judgments to {args.out}")
        return 0
    if args.command == "summarize":
        summary = summarize_records(Path(args.input))
        text = _format_summary(summary)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        print(text)
        return 0
    parser.error("unreachable")
    return 2


def _show_taxonomy(kind: str) -> None:
    if kind in {"all", "capabilities"}:
        print("Capability gaps")
        print(taxonomy_as_text(CAPABILITY_GAPS))
    if kind == "all":
        print()
    if kind in {"all", "risks"}:
        print("Risk types")
        print(taxonomy_as_text(RISK_TYPES))
    if kind == "all":
        print()
    if kind in {"all", "blindspots"}:
        print("Harness blindspots")
        print(blindspot_catalog_text(HARNESS_BLINDSPOTS))
    if kind == "all":
        print()
    if kind in {"all", "semantic-risks"}:
        print("Semantic risks")
        print(blindspot_catalog_text(SEMANTIC_RISKS))


def summarize_jsonl(path: Path) -> dict[str, Any]:
    return summarize_records(path)


def summarize_records(path: Path) -> dict[str, Any]:
    items = read_records(path)
    by_cap = Counter()
    by_risk = Counter()
    by_blindspot = Counter()
    by_semantic_risk = Counter()
    labels = Counter()
    qc_pass = Counter()
    harness_pass = Counter()
    for item in items:
        setup = item.get("setup", item)
        cap = setup.get("capability_gap") or item.get("primary_capability_gap")
        risk = setup.get("risk_type") or item.get("risk_type")
        blindspot = setup.get("harness_blindspot") or item.get("harness_blindspot")
        semantic_risk = setup.get("semantic_risk") or item.get("semantic_risk")
        if cap:
            by_cap[cap] += 1
        if risk:
            by_risk[risk] += 1
        if blindspot:
            by_blindspot[blindspot] += 1
        if semantic_risk:
            by_semantic_risk[semantic_risk] += 1
        if "label" in item:
            labels[item.get("label")] += 1
        if "quality_control" in item:
            qc_pass[str(bool(item.get("quality_control", {}).get("pass")))] += 1
        if "safeharness_precheck" in item:
            precheck = item.get("safeharness_precheck", {})
            harness_pass[str(bool(precheck.get("safeharness_allowed")) and not bool(precheck.get("l1_injection_detected")))] += 1
    return {
        "path": str(path),
        "count": len(items),
        "by_capability_gap": dict(sorted(by_cap.items())),
        "by_risk_type": dict(sorted(by_risk.items())),
        "by_harness_blindspot": dict(sorted(by_blindspot.items())),
        "by_semantic_risk": dict(sorted(by_semantic_risk.items())),
        "by_label": dict(sorted(labels.items())),
        "qc_pass": dict(sorted(qc_pass.items())),
        "safeharness_pass": dict(sorted(harness_pass.items())),
    }


def _format_summary(summary: dict[str, Any]) -> str:
    lines = [f"File: {summary['path']}", f"Count: {summary['count']}"]
    for title, key in [
        ("By capability gap", "by_capability_gap"),
        ("By risk type", "by_risk_type"),
        ("By harness blindspot", "by_harness_blindspot"),
        ("By semantic risk", "by_semantic_risk"),
        ("By label", "by_label"),
        ("QC pass", "qc_pass"),
        ("SafeHarness precheck pass", "safeharness_pass"),
    ]:
        values = summary.get(key) or {}
        if not values:
            continue
        lines.append(title + ":")
        for name, count in values.items():
            lines.append(f"  {name}: {count}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
