#!/usr/bin/env python3
"""Build one matched, full-trajectory judge panel for M / M+H / M+H+ΔH."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
M_SOURCE = ROOT / "experiments/harness实验/securitybench/raw/base_trace_panel.jsonl"
REACT_SOURCE = ROOT / "experiments/harness实验/securitybench/raw/react_arms.jsonl"
DATA = ROOT / "data/AgentSecurityBench/data"
OUTPUT = HERE / "judge_input.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logical_key(
    agent: str,
    task: str,
    attacker_tool: str,
    method: str,
    template: str,
) -> str:
    return "|".join((agent, task, attacker_tool, method.upper(), template, "0"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m-source", type=Path, default=M_SOURCE)
    parser.add_argument("--react-source", type=Path, default=REACT_SOURCE)
    parser.add_argument(
        "--delta-source",
        type=Path,
        default=None,
        help=(
            "Optional token-fixed react+safeharness source. When supplied, "
            "the react arm is read from --react-source and the delta arm is "
            "read exclusively from this file."
        ),
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Defaults to <output stem>.summary.json",
    )
    args = parser.parse_args()
    m_source = args.m_source.resolve()
    react_source = args.react_source.resolve()
    delta_source = args.delta_source.resolve() if args.delta_source else None
    output_path = args.output.resolve()
    summary_path = (
        args.summary.resolve()
        if args.summary
        else output_path.with_suffix(".summary.json")
    )

    normal_by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tool in read_jsonl(DATA / "all_normal_tools.jsonl"):
        agent = str(tool.get("Corresponding Agent") or "")
        if agent:
            normal_by_agent[agent].append(tool)
    attacks = {
        (str(row["Corresponding Agent"]), str(row["Attacker Tool"])): row
        for row in read_jsonl(DATA / "all_attack_tools.jsonl")
    }

    def normal_specs(agent: str, names: list[str]) -> list[dict[str, str]]:
        by_name = {str(tool["Tool Name"]): tool for tool in normal_by_agent[agent]}
        missing = sorted(set(names) - set(by_name))
        if missing:
            raise RuntimeError(f"normal tools missing from registry for {agent}: {missing}")
        return [
            {
                "name": name,
                "description": str(by_name[name].get("Description") or ""),
                "expected_achievement": str(by_name[name].get("Expected Achievements") or ""),
            }
            for name in names
        ]

    def attack_spec(agent: str, name: str) -> dict[str, str]:
        tool = attacks[(agent, name)]
        return {
            "name": name,
            "instruction": str(tool.get("Attacker Instruction") or ""),
            "description": str(tool.get("Description") or ""),
            "goal": str(tool.get("Attack goal") or ""),
        }

    output: list[dict[str, Any]] = []
    m_rows = [
        row
        for row in read_jsonl(m_source)
        if row.get("arm") == "base" and row.get("condition") in {"dpi", "opi"}
    ]
    for row in m_rows:
        agent = str(row["agent"])
        normal_names = [str(name) for name in row["normal_tools"]]
        attacker_name = str(row["attacker_tool"])
        method = str(row["condition"]).upper()
        key = logical_key(
            agent,
            str(row["original_task"]),
            attacker_name,
            method,
            str(row["template"]),
        )
        events = [
            {
                **event,
                "executed": True,
                "blocked": False,
                "decision": {"action": "allow", "check": "base_tool_loop"},
            }
            for event in row.get("events") or []
        ]
        output.append(
            {
                "uid": key,
                "source_uid": row["uid"],
                "arm": "M",
                "condition": method.lower(),
                "template": row["template"],
                "agent": agent,
                "original_task": row["original_task"],
                "normal_tools": normal_names,
                "normal_tool_specs": normal_specs(agent, normal_names),
                "attacker_tool": attacker_name,
                "attacker_tool_spec": attack_spec(agent, attacker_name),
                "attacker_goal": row["attacker_goal"],
                "events": events,
                "messages": row.get("messages") or [],
                "final": row.get("final") or "",
                "invalid_calls": row.get("invalid_calls") or [],
                "runner_error": row.get("error") or "",
                "marker_attack_success": bool(row.get("official_attack_success")),
                "marker_original_success": bool(row.get("both_normal_tools_called")),
                "security_blocks": 0,
                "trajectory_source": str(m_source.relative_to(ROOT)),
            }
        )

    react_rows: list[tuple[dict[str, Any], Path]] = []
    for row in read_jsonl(react_source):
        # In a clean replacement run, retain only the original ReAct control
        # from the old source. The old delta arm is intentionally excluded.
        if delta_source is not None and row.get("condition") != "react":
            continue
        react_rows.append((row, react_source))
    if delta_source is not None:
        for row in read_jsonl(delta_source):
            if row.get("condition") != "react+safeharness":
                continue
            react_rows.append((row, delta_source))

    for row, row_source in react_rows:
        if row.get("condition") not in {"react", "react+safeharness"}:
            continue
        arm = "M+H" if row["condition"] == "react" else "M+H+ΔH"
        agent = str(row["agent"])
        normal_names = [str(tool["Tool Name"]) for tool in normal_by_agent[agent]]
        attack = attacks[(agent, str(row["attacker_tool"]))]
        events = []
        invalid_calls = []
        for step in row.get("steps") or []:
            proposal = step.get("proposal") or {}
            name = proposal.get("tool")
            if not name:
                invalid_calls.append(str((step.get("decision") or {}).get("check") or "parse_error"))
                events.append(
                    {
                        "step": step.get("turn"),
                        "tool": None,
                        "arguments": {},
                        "kind": "invalid",
                        "executed": False,
                        "blocked": False,
                        "result": None,
                        "decision": step.get("decision") or {},
                    }
                )
                continue
            kind = (
                "attacker"
                if name == row["attacker_tool"]
                else ("normal" if name in normal_names else "unknown")
            )
            executed = bool(step.get("executed"))
            events.append(
                {
                    "step": step.get("turn"),
                    "tool": name,
                    "arguments": proposal.get("arguments") or {},
                    "kind": kind,
                    "executed": executed,
                    "blocked": not executed and (step.get("decision") or {}).get("action") == "block",
                    "result": step.get("observation"),
                    "decision": step.get("decision") or {},
                }
            )
        key = logical_key(
            agent,
            str(row["task"]),
            str(row["attacker_tool"]),
            str(row["method"]),
            str(row["attack_type"]),
        )
        output.append(
            {
                "uid": key,
                "source_uid": row["uid"],
                "arm": arm,
                "condition": str(row["method"]).lower(),
                "template": row["attack_type"],
                "agent": agent,
                "original_task": row["task"],
                "normal_tools": normal_names,
                "normal_tool_specs": normal_specs(agent, normal_names),
                "attacker_tool": row["attacker_tool"],
                "attacker_tool_spec": attack_spec(agent, str(row["attacker_tool"])),
                "attacker_goal": str(attack["Attack goal"]),
                "events": events,
                "messages": row.get("messages") or [],
                "final": row.get("final") or "",
                "invalid_calls": invalid_calls,
                "runner_error": row.get("error") or "",
                "marker_attack_success": bool(row.get("attack_success")),
                "marker_original_success": bool(row.get("original_success")),
                "security_blocks": int(row.get("blocked") or 0),
                "trajectory_source": str(row_source.relative_to(ROOT)),
            }
        )

    arms = Counter(row["arm"] for row in output)
    expected = Counter({"M": 600, "M+H": 600, "M+H+ΔH": 600})
    if arms != expected:
        raise RuntimeError(f"bad arm coverage: {arms}")
    key_sets = {
        arm: {row["uid"] for row in output if row["arm"] == arm}
        for arm in expected
    }
    if any(len(keys) != 600 for keys in key_sets.values()) or len({frozenset(v) for v in key_sets.values()}) != 1:
        raise RuntimeError("three arms do not cover identical 600 logical cells")
    output.sort(key=lambda row: (row["arm"], row["uid"]))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output),
        encoding="utf-8",
    )
    summary = {
        "protocol": "asb_harness_semantic_eval_v1",
        "judge_model": "deepseek-v4-pro-0813",
        "rows": len(output),
        "arms": arms,
        "logical_cells_per_arm": 600,
        "methods": Counter(row["condition"] for row in output),
        "templates": Counter(row["template"] for row in output),
        "marker_attack_success": {
            arm: sum(row["marker_attack_success"] for row in output if row["arm"] == arm)
            for arm in expected
        },
        "sources": {
            "M": {"path": str(m_source.relative_to(ROOT)), "sha256": sha256(m_source)},
            "react_control": {
                "path": str(react_source.relative_to(ROOT)),
                "sha256": sha256(react_source),
            },
            "deltaH": (
                {
                    "path": str(delta_source.relative_to(ROOT)),
                    "sha256": sha256(delta_source),
                    "token_lifecycle": "issued immediately before each generation batch",
                }
                if delta_source is not None
                else {
                    "path": str(react_source.relative_to(ROOT)),
                    "sha256": sha256(react_source),
                    "token_lifecycle": "legacy source",
                }
            ),
        },
        "output_sha256": sha256(output_path),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))


if __name__ == "__main__":
    main()
