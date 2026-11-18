#!/usr/bin/env python3
"""Build the upload-ready collaborator release from an explicit whitelist."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path


RELEASE = Path(__file__).resolve().parent
ROOT = RELEASE.parents[1]

# Destination paths are relative to RELEASE. Every source is relative to ROOT.
COPY_MAP = {
    # Three-arm Harness: frozen setting, self-contained runtime and the full
    # AutoControl trajectory+Monitor panel. SecurityBench clean outcomes are
    # added below only after the token-lifecycle audit passes.
    "harness/docs/README.md": "experiments/harness实验/README.md",
    "harness/docs/SETTING.json": "experiments/harness实验/setting.json",
    "harness/docs/RESULTS.md": "experiments/harness实验/RESULTS.md",
    "harness/docs/MANIFEST.json": "experiments/harness实验/MANIFEST.json",
    "harness/code/shared/react_protocol.py":
        "experiments/harness实验/shared/react_protocol.py",
    "harness/code/shared/safeharness_no_llm.py":
        "experiments/harness实验/shared/safeharness_no_llm.py",
    "harness/autocontrol/docs/SETTING.md":
        "experiments/harness实验/autocontrol/SETTING.md",
    "harness/autocontrol/docs/RESULTS.md":
        "experiments/harness实验/autocontrol/RESULTS.md",
    "harness/autocontrol/code/core_eval.py":
        "experiments/harness实验/autocontrol/core_eval.py",
    "harness/autocontrol/code/run_eval_react.py":
        "experiments/harness实验/autocontrol/run_eval_react.py",
    "harness/autocontrol/code/score_monitor_local.py":
        "experiments/harness实验/autocontrol/score_monitor_local.py",
    "harness/autocontrol/code/tool_tier_registry.json":
        "experiments/harness实验/autocontrol/tool_tier_registry.json",
    "harness/autocontrol/code/build_release_records.py":
        "experiments/harness实验/autocontrol/build_release_records.py",
    "harness/autocontrol/evaluation/three_arm_scored.jsonl":
        "experiments/harness实验/autocontrol/results/three_arm_scored.jsonl",
    "harness/autocontrol/evaluation/analysis.json":
        "experiments/harness实验/autocontrol/results/analysis.json",
    "harness/autocontrol/evaluation/paired_transitions.json":
        "experiments/harness实验/autocontrol/results/paired_transitions.json",
    "harness/autocontrol/evaluation/cases.json":
        "experiments/harness实验/autocontrol/results/cases.json",
    "harness/autocontrol/evaluation/AUDIT.json":
        "experiments/harness实验/autocontrol/results/AUDIT.json",
    "harness/securitybench_clean/code/canonical_eval.py":
        "experiments/harness实验/securitybench/canonical_eval.py",
    "harness/securitybench_clean/code/run_eval_react.py":
        "experiments/harness实验/securitybench/run_eval_react.py",
    "harness/securitybench_clean/code/run_eval_react_local.py":
        "experiments/harness实验/securitybench/run_eval_react_local.py",
    "harness/securitybench_clean/code/asb_tier_table_5agents_principled.json":
        "experiments/harness实验/securitybench/asb_tier_table_5agents_principled.json",
    "harness/securitybench_clean/code/requirements.txt":
        "experiments/harness实验/securitybench/requirements.txt",
    "harness/securitybench_clean/code/semantic_eval/build_judge_input.py":
        "experiments/harness实验/securitybench/semantic_eval/build_judge_input.py",
    "harness/securitybench_clean/code/semantic_eval/prepare_token_fixed_eval.py":
        "experiments/harness实验/securitybench/semantic_eval/prepare_token_fixed_eval.py",
    "harness/securitybench_clean/code/semantic_eval/judge_trajectories.py":
        "experiments/harness实验/securitybench/semantic_eval/judge_trajectories.py",
    "harness/securitybench_clean/code/semantic_eval/analyze.py":
        "experiments/harness实验/securitybench/semantic_eval/analyze.py",
    "harness/securitybench_clean/code/semantic_eval/write_manifest.py":
        "experiments/harness实验/securitybench/semantic_eval/write_manifest.py",

    # Shared evaluator code used by the formal AutoControl result.
    "shared_code/evolve/harness/scripts/ac_monitor_score.py":
        "evolve/harness/scripts/ac_monitor_score.py",
    "shared_code/evolve/harness/src/coevolve/judges/api.py":
        "evolve/harness/src/coevolve/judges/api.py",

    # AutoControl W1-only: documents and source.
    "sft/autocontrol_w1_only/docs/PROTOCOL.md":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/PROTOCOL.md",
    "sft/autocontrol_w1_only/docs/SETTING.json":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/SETTING.json",
    "sft/autocontrol_w1_only/docs/STATUS.md":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/STATUS.md",
    "sft/autocontrol_w1_only/code/build_dataset.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/build_dataset.py",
    "sft/autocontrol_w1_only/code/validate_tokenization.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/validate_tokenization.py",
    "sft/autocontrol_w1_only/code/training/launch_job.sh":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/training/launch_job.sh",
    "sft/autocontrol_w1_only/code/training/submit_rjob.sh":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/training/submit_rjob.sh",
    "sft/autocontrol_w1_only/code/evaluation/analyze_three_arm.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/analyze_three_arm.py",
    "sft/autocontrol_w1_only/code/evaluation/assemble_three_arm.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/assemble_three_arm.py",
    "sft/autocontrol_w1_only/code/evaluation/render_case_inventory.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/render_case_inventory.py",
    "sft/autocontrol_w1_only/code/evaluation/prepare_monitor_shards.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/prepare_monitor_shards.py",
    "sft/autocontrol_w1_only/code/evaluation/merge_monitor_shards.py":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/merge_monitor_shards.py",
    "sft/autocontrol_w1_only/code/evaluation/launch_sft.sh":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/launch_sft.sh",
    "sft/autocontrol_w1_only/code/evaluation/submit_sft_rjob.sh":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/submit_sft_rjob.sh",
    "sft/autocontrol_w1_only/training_data/train.jsonl":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/data/train.jsonl",
    "sft/autocontrol_w1_only/training_data/manifest.json":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/data/manifest.json",
    "sft/autocontrol_w1_only/training_data/tokenization_report.json":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/data/tokenization_report.json",
    "sft/autocontrol_w1_only/evaluation/three_arm.jsonl":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/runs/t1_three_rollouts/scored/three_arm.jsonl",
    "sft/autocontrol_w1_only/evaluation/summary.json":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/runs/t1_three_rollouts/scored/three_arm.summary.json",
    "sft/autocontrol_w1_only/evaluation/analysis.json":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/results/analysis.json",
    "sft/autocontrol_w1_only/evaluation/REPORT.md":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/results/REPORT.md",
    "sft/autocontrol_w1_only/evaluation/INSIGHTS_CN.md":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/results/INSIGHTS_CN.md",
    "sft/autocontrol_w1_only/evaluation/CASE_INVENTORY.md":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/results/CASE_INVENTORY.md",
    "sft/autocontrol_w1_only/evaluation/paired_transitions.jsonl":
        "experiments/model_vs_harness_sft/autocontrol_w1_only/evaluation/runs/t1_three_rollouts/analysis/paired_transitions.jsonl",

    # SecurityBench v2: documents and source.
    "sft/securitybench_v2/docs/PROTOCOL.md":
        "experiments/model_vs_harness_sft/securitybench_v2/PROTOCOL.md",
    "sft/securitybench_v2/docs/RESULTS_CN.md":
        "experiments/model_vs_harness_sft/securitybench_v2/RESULTS_CN.md",
    "sft/securitybench_v2/docs/RUN_MANIFEST.json":
        "experiments/model_vs_harness_sft/securitybench_v2/RUN_MANIFEST.json",
    "sft/securitybench_v2/code/build_contracts.py":
        "experiments/model_vs_harness_sft/securitybench_v2/build_contracts.py",
    "sft/securitybench_v2/code/compile_dataset.py":
        "experiments/model_vs_harness_sft/securitybench_v2/compile_dataset.py",
    "sft/securitybench_v2/code/normalize_contracts.py":
        "experiments/model_vs_harness_sft/securitybench_v2/normalize_contracts.py",
    "sft/securitybench_v2/code/recover_contracts.py":
        "experiments/model_vs_harness_sft/securitybench_v2/recover_contracts.py",
    "sft/securitybench_v2/code/training/dry_run.py":
        "experiments/model_vs_harness_sft/securitybench_v2/training/dry_run.py",
    "sft/securitybench_v2/code/training/launch_job.sh":
        "experiments/model_vs_harness_sft/securitybench_v2/training/launch_job.sh",
    "sft/securitybench_v2/code/training/submit_rjob.sh":
        "experiments/model_vs_harness_sft/securitybench_v2/training/submit_rjob.sh",
    "sft/securitybench_v2/code/evaluation/run_eval.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/run_eval.py",
    "sft/securitybench_v2/code/evaluation/score_results.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/score_results.py",
    "sft/securitybench_v2/code/evaluation/analyze_scored.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/analyze_scored.py",
    "sft/securitybench_v2/code/evaluation/make_case_report.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/make_case_report.py",
    "sft/securitybench_v2/code/evaluation/build_manifest.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/build_manifest.py",
    "sft/securitybench_v2/code/evaluation/build_dev_selection.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/build_dev_selection.py",
    "sft/securitybench_v2/code/evaluation/build_test_selection.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/build_test_selection.py",
    "sft/securitybench_v2/code/evaluation/validate_design.py":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/validate_design.py",
    "sft/securitybench_v2/training_data/train.jsonl":
        "experiments/model_vs_harness_sft/securitybench_v2/output/sft/train.jsonl",
    "sft/securitybench_v2/training_data/manifest.json":
        "experiments/model_vs_harness_sft/securitybench_v2/output/sft/manifest.json",
    "sft/securitybench_v2/training_data/tokenization_report.json":
        "experiments/model_vs_harness_sft/securitybench_v2/output/sft/tokenization_report.json",
    "sft/securitybench_v2/evaluation/test_manifest.jsonl":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/manifests/test.jsonl",
    "sft/securitybench_v2/evaluation/test_selection.json":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/manifests/test_selection.json",
    "sft/securitybench_v2/evaluation/test_selection.jsonl":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/manifests/test_selection.jsonl",
    "sft/securitybench_v2/evaluation/judged.jsonl":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/runs/frozen_test/scored/judged.jsonl",
    "sft/securitybench_v2/evaluation/judge_summary.json":
        "experiments/model_vs_harness_sft/securitybench_v2/evaluation/runs/frozen_test/scored/summary.json",
    "sft/securitybench_v2/evaluation/analysis.json":
        "experiments/model_vs_harness_sft/securitybench_v2/results/analysis.json",
    "sft/securitybench_v2/evaluation/CASES.md":
        "experiments/model_vs_harness_sft/securitybench_v2/results/CASES.md",

    # Upward Deception: documents and source.
    "sft/upward_deception/docs/README.md":
        "experiments/model_vs_harness_sft/upward_deception/README.md",
    "sft/upward_deception/docs/PROTOCOL.md":
        "experiments/model_vs_harness_sft/upward_deception/PROTOCOL.md",
    "sft/upward_deception/docs/EVAL_PROTOCOL.md":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/EVAL_PROTOCOL.md",
    "sft/upward_deception/code/build_gold_dataset.py":
        "experiments/model_vs_harness_sft/upward_deception/build_gold_dataset.py",
    "sft/upward_deception/code/training/data.py":
        "experiments/model_vs_harness_sft/upward_deception/training/data.py",
    "sft/upward_deception/code/training/dry_run.py":
        "experiments/model_vs_harness_sft/upward_deception/training/dry_run.py",
    "sft/upward_deception/code/training/train.py":
        "experiments/model_vs_harness_sft/upward_deception/training/train.py",
    "sft/upward_deception/code/training/run_with_gpu_monitor.py":
        "experiments/model_vs_harness_sft/upward_deception/training/run_with_gpu_monitor.py",
    "sft/upward_deception/code/training/launch_job.sh":
        "experiments/model_vs_harness_sft/upward_deception/training/launch_job.sh",
    "sft/upward_deception/code/training/submit_rjob.sh":
        "experiments/model_vs_harness_sft/upward_deception/training/submit_rjob.sh",
    "sft/upward_deception/code/training/requirements.txt":
        "experiments/model_vs_harness_sft/upward_deception/training/requirements.txt",
    "sft/upward_deception/code/evaluation/run_local_eval.py":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/run_local_eval.py",
    "sft/upward_deception/code/evaluation/judge_eval.py":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/judge_eval.py",
    "sft/upward_deception/code/evaluation/analyze_results.py":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/analyze_results.py",
    "sft/upward_deception/training_data/train.jsonl":
        "experiments/model_vs_harness_sft/upward_deception/output/sft/train.jsonl",
    "sft/upward_deception/training_data/manifest.json":
        "experiments/model_vs_harness_sft/upward_deception/output/sft/manifest.json",
    "sft/upward_deception/training_data/quality_report.json":
        "experiments/model_vs_harness_sft/upward_deception/output/sft/quality_report.json",
    "sft/upward_deception/training_data/tokenization_report.json":
        "experiments/model_vs_harness_sft/upward_deception/training/tokenization_report.json",
    "sft/upward_deception/evaluation/frozen_test_manifest.json":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/frozen_test_manifest.json",
    "sft/upward_deception/evaluation/judged_records.jsonl":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/runs/paired_test_v2_clean/judged/judged_records.jsonl",
    "sft/upward_deception/evaluation/judge_summary.json":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/runs/paired_test_v2_clean/judged/summary.json",
    "sft/upward_deception/evaluation/analysis.json":
        "experiments/model_vs_harness_sft/upward_deception/results/analysis.json",
    "sft/upward_deception/evaluation/cases.json":
        "experiments/model_vs_harness_sft/upward_deception/evaluation/runs/paired_test_v2_clean/analysis/cases.json",
    "sft/upward_deception/evaluation/REPORT_ZH.md":
        "experiments/model_vs_harness_sft/upward_deception/results/REPORT_ZH.md",
    "sft/upward_deception/evaluation/CASES_ZH.md":
        "experiments/model_vs_harness_sft/upward_deception/results/CASES_ZH.md",
}


FORBIDDEN_PARTS = {
    "training/runs",
    "previous",
    "invalid",
    "smoke",
    "__pycache__",
    "checkpoint-",
    "final_adapter",
}
FORBIDDEN_SUFFIXES = {".pt", ".pth", ".bin", ".safetensors", ".pyc", ".log"}
SECRET_PATTERNS = (
    # Long legacy/gateway tokens such as sk-<hex or base62>. Requiring a
    # continuous token avoids false positives from prose/URLs containing
    # words such as "risk-analysis".
    re.compile(rb"(?<![A-Za-z0-9])sk-[A-Za-z0-9]{20,}"),
    # Common structured key families.
    re.compile(rb"(?<![A-Za-z0-9])sk-(?:proj|live|test)-[A-Za-z0-9_-]{20,}"),
)
MAX_FILE_BYTES = 64 * 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_relative(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path: {path_text}")
    lowered = path_text.lower()
    if any(part in lowered for part in FORBIDDEN_PARTS):
        raise ValueError(f"forbidden path component: {path_text}")
    if path.suffix.lower() in FORBIDDEN_SUFFIXES or ".partial." in lowered:
        raise ValueError(f"forbidden file type: {path_text}")
    return path


def validate_file(path: Path) -> None:
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ValueError(f"oversized release file ({size} bytes): {path}")
    content = path.read_bytes()
    if any(pattern.search(content) for pattern in SECRET_PATTERNS):
        raise ValueError(f"possible plaintext API key in {path}")


def main() -> None:
    copy_map = dict(COPY_MAP)
    clean_root = Path("experiments/harness实验/securitybench/semantic_eval")
    clean_sources = {
        "harness/securitybench_clean/evaluation/judged.jsonl":
            clean_root / "results/judged.jsonl",
        "harness/securitybench_clean/evaluation/judge_input.summary.json":
            clean_root / "judge_input.summary.json",
        "harness/securitybench_clean/evaluation/analysis.json":
            clean_root / "results/analysis.json",
        "harness/securitybench_clean/evaluation/paired_transitions.json":
            clean_root / "results/paired_transitions.json",
        "harness/securitybench_clean/evaluation/cases.json":
            clean_root / "results/cases.json",
        "harness/securitybench_clean/evaluation/REPORT.md":
            clean_root / "results/REPORT.md",
        "harness/securitybench_clean/evaluation/CASES.md":
            clean_root / "results/CASES.md",
        "harness/securitybench_clean/evaluation/MANIFEST.json":
            clean_root / "results/MANIFEST.json",
        "harness/securitybench_clean/evaluation/CONTROL_REUSE_AUDIT.json":
            clean_root / "results/CONTROL_REUSE_AUDIT.json",
    }
    clean_manifest_path = ROOT / clean_root / "results/MANIFEST.json"
    clean_complete = all((ROOT / source).is_file() for source in clean_sources.values())
    if clean_complete:
        clean_manifest = json.loads(clean_manifest_path.read_text(encoding="utf-8"))
        clean_complete = clean_manifest.get("status") == "complete_clean"
    if clean_complete:
        copy_map.update(
            {
                destination: source.as_posix()
                for destination, source in clean_sources.items()
            }
        )

    # Remove only generated payload namespaces inside this release. The
    # hand-written README and SETTING remain source-controlled metadata.
    for generated_name in ("sft", "shared_code", "harness", "__pycache__"):
        generated = RELEASE / generated_name
        if generated.exists():
            shutil.rmtree(generated)

    source_by_destination: dict[str, str] = {}
    for destination_text, source_text in sorted(copy_map.items()):
        destination_relative = validate_relative(destination_text)
        source_relative = validate_relative(source_text)
        source = (ROOT / source_relative).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"missing whitelisted source: {source_relative}")
        if ROOT not in source.parents:
            raise ValueError(f"source escaped repository: {source}")
        validate_file(source)
        destination = RELEASE / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        source_by_destination[destination_relative.as_posix()] = source_relative.as_posix()

    # The frozen AutoControl M arm predates message-level serialization: its
    # records contain the complete action/observation steps but an empty
    # `messages` list.  Ship the exact 240 task specs referenced by all three
    # arms so collaborators still have the initial task, tool schemas and
    # simulator state without duplicating that context into 2,160 rows.
    panel_source_relative = Path(
        "experiments/harness实验/autocontrol/results/three_arm_scored.jsonl"
    )
    panel_source = ROOT / panel_source_relative
    spec_sources: set[str] = set()
    with panel_source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            spec_path = record.get("spec_path")
            if not isinstance(spec_path, str) or not spec_path:
                raise ValueError(f"missing spec_path at {panel_source}:{line_number}")
            spec_sources.add(spec_path)
    if len(spec_sources) != 240:
        raise ValueError(f"expected 240 frozen AutoControl specs, got {len(spec_sources)}")

    spec_index = []
    seen_names: set[str] = set()
    for source_text in sorted(spec_sources):
        source_relative = validate_relative(source_text)
        source = (ROOT / source_relative).resolve()
        if not source.is_file() or ROOT not in source.parents:
            raise FileNotFoundError(f"missing referenced task spec: {source_relative}")
        validate_file(source)
        if source.name in seen_names:
            raise ValueError(f"duplicate task-spec basename: {source.name}")
        seen_names.add(source.name)
        destination_relative = Path(
            "harness/autocontrol/evaluation/task_specs"
        ) / source.name
        destination = RELEASE / destination_relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        source_by_destination[destination_relative.as_posix()] = source_relative.as_posix()
        spec_index.append(
            {
                "trajectory_spec_path": source_relative.as_posix(),
                "release_path": destination_relative.as_posix(),
                "sha256": sha256(source),
            }
        )
    spec_index_relative = Path("harness/autocontrol/evaluation/task_specs/index.json")
    spec_index_path = RELEASE / spec_index_relative
    spec_index_path.write_text(
        json.dumps({"count": len(spec_index), "specs": spec_index}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    source_by_destination[spec_index_relative.as_posix()] = (
        "derived from " + panel_source_relative.as_posix()
    )

    manifest_files = []
    for path in sorted(RELEASE.rglob("*")):
        if not path.is_file() or path.name == "MANIFEST.json":
            continue
        relative = path.relative_to(RELEASE)
        validate_relative(relative.as_posix())
        validate_file(path)
        manifest_files.append(
            {
                "path": relative.as_posix(),
                "source": source_by_destination.get(relative.as_posix(), "release_metadata"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    manifest = {
        "protocol": "collaborator_release_manifest_v1",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "file_count": len(manifest_files),
        "total_bytes": sum(item["bytes"] for item in manifest_files),
        "securitybench_clean_harness_status": (
            "complete" if clean_complete else "pending"
        ),
        "secret_scan": {
            "patterns": [
                "standalone sk- followed by at least 20 continuous alphanumeric characters",
                "standalone sk-(proj|live|test)- followed by at least 20 key characters"
            ],
            "matches": 0,
        },
        "files": manifest_files,
    }
    (RELEASE / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "files": manifest["file_count"],
                "bytes": manifest["total_bytes"],
                "manifest": str(RELEASE / "MANIFEST.json"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
