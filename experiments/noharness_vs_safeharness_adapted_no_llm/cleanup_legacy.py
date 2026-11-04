#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path


EXPERIMENTS = Path(__file__).resolve().parent.parent
CANONICAL = Path(__file__).resolve().parent
PREVIOUS = EXPERIMENTS / "previous"
ARCHIVE = PREVIOUS / "pre_canonical_20261104"

KEEP_TOP_LEVEL = {
    "README.md",
    "figures",
    "noharness_vs_safeharness_adapted_no_llm",
    "previous",
}

DELETE_MARKERS = ("pilot", "smoke", "invalid", "stale")

EXPLICIT_OBSOLETE = [
    PREVIOUS / "safeharness_true_threshold_gpt4omini",
    PREVIOUS / "risk_resplit/run100_l2ablation",
    PREVIOUS / "risk_resplit/asb_l2ablation_results.jsonl",
    PREVIOUS / "risk_resplit/asb_mp_l2ablation.jsonl",
    PREVIOUS / "risk_resplit/asb_pot_l2ablation.jsonl",
    PREVIOUS / "risk_resplit/asb_l2ablation_results.summary.json",
    PREVIOUS / "pre_canonical_20261104/autocontrol_core/plus_l2_original_threshold",
    # Old AutoControl arms using runtime LLM/final L2, or duplicate copies of the
    # now-canonical no-LLM results.
    PREVIOUS / "pre_canonical_20261104/safeharness_adapted_no_llm",
    PREVIOUS / "pre_canonical_20261104/safeharness_adapted_v2",
    PREVIOUS / "pre_canonical_20261104/safeharness_l2",
    PREVIOUS / "pre_canonical_20261104/safeharness_l2action",
    PREVIOUS / "pre_canonical_20261104/safeharness_replay",
    PREVIOUS / "pre_canonical_20261104/ac_ic_oe_sg_st",
    PREVIOUS / "pre_canonical_20261104/ac_cw_ea_sm_st",
    # Old SecurityBench variants: keyword-only, attacker-register/open-book,
    # benchmark-specific injected-target matching, and duplicate general-taint
    # copies. Only the canonical general-taint records are retained.
    PREVIOUS / "pre_canonical_20261104/risk_resplit/ASB_GLM_TIERS_REPORT.md",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/adapted_no_llm_launcher.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/adapted_no_llm_run.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/adapted_no_llm_run_v2.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/adapted_no_llm_v2_launcher.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_adapted_no_llm_dpi_opi.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_adapted_no_llm_dpi_opi.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_adapted_no_llm_dpi_opi_v2.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_adapted_no_llm_memory.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_full_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_full_results.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_general_taint_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_general_taint_results.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_general_taint_run.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_glm_tiers_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_glm_tiers_results.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_glm_tiers_run.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_principled_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_principled_results.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_principled_run.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_tier_table_5agents.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_tier_table_5agents_principled.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_tool_inventory_5agents.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/label_asb_principled.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/label_asb_tiers.log",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/label_asb_tiers.py",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/label_asb_tiers_principled.py",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/run_adapted_no_llm_all.sh",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/run_adapted_no_llm_dpi_opi_v2.sh",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/run_asb_glm_tiers.sh",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/run_asb_principled.sh",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_mp_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_mp_results2.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_mp_results2.summary.json",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_pot_results.jsonl",
    PREVIOUS / "pre_canonical_20261104/risk_resplit/asb_pot_results.summary.json",
]


def remove_path(path: Path, deleted: list[str]) -> None:
    if not path.exists() and not path.is_symlink():
        return
    deleted.append(str(path.relative_to(EXPERIMENTS)))
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def main() -> None:
    PREVIOUS.mkdir(exist_ok=True)
    ARCHIVE.mkdir(exist_ok=True)
    deleted: list[str] = []
    archived: list[dict[str, str]] = []

    # Explicitly remove test-only or known-obsolete experiment families anywhere
    # outside the canonical directory. Traverse deepest-first.
    candidates = sorted(
        (
            path
            for path in EXPERIMENTS.rglob("*")
            if CANONICAL not in path.parents
            and any(marker in path.name.lower() for marker in DELETE_MARKERS)
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in candidates:
        if path.exists() or path.is_symlink():
            remove_path(path, deleted)

    for path in EXPLICIT_OBSOLETE:
        remove_path(path, deleted)

    # Move every remaining noncanonical top-level artifact into one dated archive.
    for source in sorted(EXPERIMENTS.iterdir(), key=lambda path: path.name):
        if source.name in KEEP_TOP_LEVEL:
            continue
        target = ARCHIVE / source.name
        if target.exists() or target.is_symlink():
            raise RuntimeError(f"archive collision: {target}")
        shutil.move(str(source), str(target))
        archived.append(
            {
                "source": source.name,
                "target": str(target.relative_to(EXPERIMENTS)),
            }
        )

    old_report_path = CANONICAL / "cleanup_report.json"
    old_report = {}
    if old_report_path.exists():
        old_report = json.loads(old_report_path.read_text(encoding="utf-8"))
    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "canonical": str(CANONICAL.relative_to(EXPERIMENTS)),
        "archive": str(ARCHIVE.relative_to(EXPERIMENTS)),
        "deleted": sorted(set(old_report.get("deleted", [])) | set(deleted)),
        "archived": old_report.get("archived", []) + archived,
    }
    (CANONICAL / "cleanup_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(
        {
            "deleted_count": len(report["deleted"]),
            "archived_count": len(archived),
            "archive": report["archive"],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
