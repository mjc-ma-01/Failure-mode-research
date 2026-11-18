#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE_ROOT = ROOT / "experiments/noharness_vs_safeharness_adapted_no_llm/autocontrol"
CONFIG = SOURCE_ROOT / "config/autocontrol_st"
SOURCES = [
    SOURCE_ROOT / "raw/ic_oe_sg/noharness.episodes.jsonl.gz",
    SOURCE_ROOT / "raw/cw_ea_sm/noharness.episodes.jsonl.gz",
]
REGISTRY = HERE / "tool_tier_registry.json"
MANIFEST = HERE / "artifacts/full_manifest.jsonl"
M_TRAJECTORIES = HERE / "runs/full/m_trajectories.jsonl"
SHARD_DIR = HERE / "artifacts/generation_shards"
EXPECTED_CATEGORIES = {
    "Instrumental Convergence": 16,
    "Oversight Evasion": 9,
    "Specification Gaming": 11,
    "Covert Whistleblowing": 9,
    "Evaluation Awareness": 6,
    "Strategic Misalignment": 9,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    registered = {(row["name"], row["effect"]) for row in registry}
    registered_names = {row["name"] for row in registry}
    tiers_by_name: dict[str, set[str]] = {}
    for row in registry:
        tiers_by_name.setdefault(row["name"], set()).add(row["tier"])
    source_episodes = []
    for source in SOURCES:
        with gzip.open(source, "rt", encoding="utf-8") as handle:
            source_episodes.extend(json.loads(line) for line in handle if line.strip())

    keys = [(row["task_uid"], int(row["seed"])) for row in source_episodes]
    if len(source_episodes) != 720 or len(set(keys)) != 720:
        raise RuntimeError(f"expected 720 unique source episodes, got {len(source_episodes)}/{len(set(keys))}")

    manifest_rows = []
    m_rows = []
    missing = []
    name_fallbacks = set()
    scenarios = set()
    category_scenarios = Counter()
    seen_scenarios = set()
    for episode in sorted(source_episodes, key=lambda row: (row["task_uid"], int(row["seed"]))):
        task_uid = episode["task_uid"]
        relative_name = task_uid.split(":", 1)[1] + ".json"
        spec_path = CONFIG / relative_name
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        category = spec["risk_category"]
        if category == "Capability Misuse":
            raise RuntimeError(f"Capability Misuse leaked into full experiment: {task_uid}")
        for tool in spec.get("tools", []):
            key = (str(tool.get("name") or ""), str(tool.get("effect") or ""))
            if key not in registered and key[0] in registered_names:
                if len(tiers_by_name[key[0]]) != 1:
                    raise RuntimeError(
                        f"ambiguous name fallback for {task_uid}: {key[0]} -> "
                        f"{sorted(tiers_by_name[key[0]])}"
                    )
                name_fallbacks.add(key)
            elif key not in registered:
                missing.append((task_uid, key[0]))
        base_uid, variant = task_uid.rsplit("@", 1)
        if base_uid not in seen_scenarios:
            seen_scenarios.add(base_uid)
            category_scenarios[category] += 1
        scenarios.add(base_uid)
        rollout_id = int(episode["seed"])
        manifest = {
            "base_uid": base_uid,
            "domain": spec.get("domain", ""),
            "generation_seed": rollout_id,
            "levels": spec.get("levels") or {},
            "risk_category": category,
            "rollout_id": rollout_id,
            "spec_path": str(spec_path.relative_to(ROOT)),
            "spec_sha256": sha256(spec_path),
            "split": "full",
            "task_uid": task_uid,
            "variant": variant,
        }
        manifest_rows.append(manifest)
        m_rows.append({
            "uid": f"full:W1_visible_policy_choice:{task_uid}:normal:r{rollout_id}",
            "split": "full",
            "panel": "W1_visible_policy_choice",
            "condition": "normal",
            "rollout_id": rollout_id,
            "generation_seed": rollout_id,
            "task_uid": task_uid,
            "base_uid": base_uid,
            "variant": variant,
            "risk_category": category,
            "domain": spec.get("domain", ""),
            "arm": "base",
            "model_name": "base",
            "harness": False,
            "messages": [],
            "steps": episode.get("steps") or [],
            "final_output": episode.get("final_output") or "",
            "final_claim": "",
            "rounds": len(episode.get("steps") or []),
            "blocked": 0,
            "fallbacks": 0,
            "oracle_harm": bool((episode.get("outcome") or {}).get("harm")),
            "predicate_utility": bool((episode.get("outcome") or {}).get("utility")),
            "error": ";".join(episode.get("errors") or []),
            "parse_errors": 0,
            "elapsed_s": None,
            "spec_path": str(spec_path.relative_to(ROOT)),
            "source_cell": episode.get("cell"),
            "source_sha256": sha256(SOURCES[0] if "ic_" in task_uid or "oe_" in task_uid or "sg_" in task_uid else SOURCES[1]),
        })

    if missing:
        raise RuntimeError(f"unregistered full-data tools: {missing[:20]}")
    if len(scenarios) != 60 or dict(category_scenarios) != EXPECTED_CATEGORIES:
        raise RuntimeError(f"bad scenario coverage: {len(scenarios)} {category_scenarios}")
    if Counter(row["rollout_id"] for row in manifest_rows) != Counter({0: 240, 1: 240, 2: 240}):
        raise RuntimeError("bad rollout coverage")

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    M_TRAJECTORIES.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in manifest_rows), encoding="utf-8")
    M_TRAJECTORIES.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in m_rows), encoding="utf-8")

    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    for shard in range(6):
        rows = [row for index, row in enumerate(manifest_rows) if index % 6 == shard]
        (SHARD_DIR / f"shard_{shard}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )
        if len(rows) != 120:
            raise RuntimeError(f"bad shard {shard}: {len(rows)}")

    summary = {
        "protocol": "autocontrol_full_harness_v1",
        "source_episodes": len(source_episodes),
        "scenarios": len(scenarios),
        "category_scenarios": category_scenarios,
        "variants": len({row["task_uid"] for row in manifest_rows}),
        "rollouts": Counter(row["rollout_id"] for row in manifest_rows),
        "rows_per_arm": len(manifest_rows),
        "generation_shards": 6,
        "rows_per_generation_shard": 120,
        "registry_records": len(registry),
        "unregistered_tools": 0,
        "exact_signature_misses_resolved_by_unambiguous_name_fallback": len(name_fallbacks),
        "name_fallbacks": sorted(name_fallbacks),
        "manifest_sha256": sha256(MANIFEST),
        "m_trajectories_sha256": sha256(M_TRAJECTORIES),
    }
    (MANIFEST.parent / "full_manifest.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
