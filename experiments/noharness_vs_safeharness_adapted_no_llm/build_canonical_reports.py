#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_jsonl(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def category(uid: str) -> str:
    task = uid.split(":", 1)[1].split("@", 1)[0]
    return task.split("_", 1)[0].upper()


def ac_monitor(path: Path) -> dict[tuple[str, int], dict]:
    output = {}
    for row in read_jsonl(path):
        uid, _, seed = row["cell"].rpartition("#")
        output[(uid, int(seed))] = row
    return output


def ac_episodes(path: Path) -> dict[tuple[str, int], dict]:
    return {(row["task_uid"], int(row["seed"])): row for row in read_jsonl(path)}


def blocked_steps(episode: dict) -> list[dict]:
    return [
        step
        for step in episode.get("steps", [])
        if (step.get("decision") or {}).get("action") == "block"
    ]


def short_action(step: dict) -> str:
    proposal = step.get("proposal") or {}
    decision = step.get("decision") or {}
    arguments = json.dumps(proposal.get("arguments") or {}, ensure_ascii=False)
    if len(arguments) > 180:
        arguments = arguments[:177] + "..."
    suffix = ""
    if decision.get("action") == "block":
        suffix = f" ⊘BLOCK[{decision.get('check') or 'unknown'}]"
    return f"{proposal.get('tool', '?')}({arguments}){suffix}"


def build_autocontrol() -> None:
    base = ROOT / "autocontrol"
    groups = {
        "ic_oe_sg": base / "raw/ic_oe_sg",
        "cw_ea_sm": base / "raw/cw_ea_sm",
    }
    aggregate: dict[str, dict] = {}
    transitions: Counter = Counter()
    transition_blocks: Counter = Counter()
    cases: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for group_name, directory in groups.items():
        monitors = {
            "noharness": ac_monitor(directory / "noharness.monitor.jsonl"),
            "safeharness_adapted_no_llm": ac_monitor(
                directory / "adapted_no_llm.monitor.jsonl"
            ),
        }
        episodes = {
            "noharness": ac_episodes(directory / "noharness.episodes.jsonl.gz"),
            "safeharness_adapted_no_llm": ac_episodes(
                directory / "adapted_no_llm.episodes.jsonl.gz"
            ),
        }
        for condition, rows in monitors.items():
            for key, row in rows.items():
                if not row.get("parse_ok"):
                    continue
                cat = category(key[0])
                stats = aggregate.setdefault(cat, {}).setdefault(
                    condition,
                    {
                        "n": 0,
                        "risky_n": 0,
                        "helpfulness_sum": 0.0,
                        "task_success_n": 0,
                        "blocked_episodes": 0,
                        "blocked_calls": 0,
                        "layers": Counter(),
                        "proposal_parse_error_episodes": 0,
                        "max_steps_episodes": 0,
                    },
                )
                episode = episodes[condition][key]
                stats["n"] += 1
                stats["risky_n"] += int(bool(row.get("is_risky")))
                stats["helpfulness_sum"] += float(row.get("helpfulness") or 0)
                stats["task_success_n"] += int(bool(row.get("task_success")))
                stats["proposal_parse_error_episodes"] += int(bool(episode.get("errors")))
                stats["max_steps_episodes"] += int(episode.get("termination") == "max_steps")
                blocked = blocked_steps(episode)
                stats["blocked_episodes"] += int(bool(blocked))
                stats["blocked_calls"] += len(blocked)
                stats["layers"].update(
                    (step.get("decision") or {}).get("check") or "unknown"
                    for step in blocked
                )

        no_harness = monitors["noharness"]
        adapted = monitors["safeharness_adapted_no_llm"]
        for key in sorted(no_harness):
            if key not in adapted:
                continue
            left, right = no_harness[key], adapted[key]
            if not (left.get("parse_ok") and right.get("parse_ok")):
                continue
            cat = category(key[0])
            before = bool(left["is_risky"])
            after = bool(right["is_risky"])
            transitions[(cat, before, after)] += 1
            adapted_blocked = bool(blocked_steps(episodes["safeharness_adapted_no_llm"][key]))
            transition_blocks[(cat, before, after, adapted_blocked)] += 1
            case_type = (
                "risk_down"
                if before and not after
                else "risk_remains"
                if before and after
                else "risk_up"
                if not before and after
                else "safe_remains"
            )
            if len(cases[cat][case_type]) >= 5:
                continue
            no_episode = episodes["noharness"][key]
            adapted_episode = episodes["safeharness_adapted_no_llm"][key]
            cases[cat][case_type].append(
                {
                    "task_uid": key[0],
                    "seed": key[1],
                    "noharness": {
                        "is_risky": before,
                        "helpfulness": left.get("helpfulness"),
                        "task_success": left.get("task_success"),
                        "actions": [short_action(step) for step in no_episode.get("steps", [])],
                        "final": no_episode.get("final_output", ""),
                    },
                    "safeharness_adapted_no_llm": {
                        "is_risky": after,
                        "helpfulness": right.get("helpfulness"),
                        "task_success": right.get("task_success"),
                        "actions": [
                            short_action(step) for step in adapted_episode.get("steps", [])
                        ],
                        "final": adapted_episode.get("final_output", ""),
                    },
                }
            )

    total = {}
    normalized = {}
    for cat, arms in sorted(aggregate.items()):
        normalized[cat] = {}
        for condition, stats in arms.items():
            n = stats["n"]
            normalized[cat][condition] = {
                "n": n,
                "risky_n": stats["risky_n"],
                "risky_rate": round(stats["risky_n"] / n, 4),
                "helpfulness_mean": round(stats["helpfulness_sum"] / n, 4),
                "task_success_n": stats["task_success_n"],
                "task_success_rate": round(stats["task_success_n"] / n, 4),
                "blocked_episodes": stats["blocked_episodes"],
                "blocked_calls": stats["blocked_calls"],
                "layers": dict(stats["layers"]),
                "proposal_parse_error_episodes": stats["proposal_parse_error_episodes"],
                "max_steps_episodes": stats["max_steps_episodes"],
            }
            target = total.setdefault(
                condition,
                {
                    "n": 0,
                    "risky_n": 0,
                    "helpfulness_sum": 0.0,
                    "task_success_n": 0,
                    "blocked_episodes": 0,
                    "blocked_calls": 0,
                    "layers": Counter(),
                    "proposal_parse_error_episodes": 0,
                    "max_steps_episodes": 0,
                },
            )
            for key in (
                "n",
                "risky_n",
                "helpfulness_sum",
                "task_success_n",
                "blocked_episodes",
                "blocked_calls",
                "proposal_parse_error_episodes",
                "max_steps_episodes",
            ):
                target[key] += stats[key]
            target["layers"].update(stats["layers"])
    total_normalized = {}
    for condition, stats in total.items():
        n = stats["n"]
        total_normalized[condition] = {
            "n": n,
            "risky_n": stats["risky_n"],
            "risky_rate": round(stats["risky_n"] / n, 4),
            "helpfulness_mean": round(stats["helpfulness_sum"] / n, 4),
            "task_success_n": stats["task_success_n"],
            "task_success_rate": round(stats["task_success_n"] / n, 4),
            "blocked_episodes": stats["blocked_episodes"],
            "blocked_calls": stats["blocked_calls"],
            "layers": dict(stats["layers"]),
            "proposal_parse_error_episodes": stats["proposal_parse_error_episodes"],
            "max_steps_episodes": stats["max_steps_episodes"],
        }
    transition_json = {
        cat: {
            f"{int(before)}->{int(after)}": count
            for (row_cat, before, after), count in sorted(transitions.items())
            if row_cat == cat
        }
        for cat in sorted({key[0] for key in transitions})
    }
    transition_block_json = {
        cat: {
            f"{int(before)}->{int(after)}|blocked={str(blocked).lower()}": count
            for (row_cat, before, after, blocked), count in sorted(transition_blocks.items())
            if row_cat == cat
        }
        for cat in sorted({key[0] for key in transition_blocks})
    }
    write_json(
        base / "results.json",
        {
            "judge": "AutoControl official-rubric Monitor, Qwen/Qwen3-32B",
            "by_category": normalized,
            "overall": total_normalized,
            "paired_transitions": transition_json,
            "paired_transitions_by_adapted_block": transition_block_json,
        },
    )
    write_json(base / "cases.json", cases)

    lines = [
        "# AutoControl results",
        "",
        "Outcome labels are from the offline AutoControl-rubric Monitor, not from SafeHarness.",
        "",
        "| Category | n/arm | No harness risky / task success | Adapted no-LLM risky / task success | Blocks |",
        "|---|---:|---:|---:|---:|",
    ]
    for cat, arms in normalized.items():
        left = arms["noharness"]
        right = arms["safeharness_adapted_no_llm"]
        lines.append(
            f"| {cat} | {left['n']} | {left['risky_rate']:.1%} / "
            f"{left['task_success_rate']:.1%} | {right['risky_rate']:.1%} / "
            f"{right['task_success_rate']:.1%} | "
            f"{right['blocked_episodes']} episodes, {right['blocked_calls']} calls |"
        )
    left = total_normalized["noharness"]
    right = total_normalized["safeharness_adapted_no_llm"]
    lines.append(
        f"| **Overall** | **{left['n']}** | **{left['risky_rate']:.1%} / "
        f"{left['task_success_rate']:.1%}** | **{right['risky_rate']:.1%} / "
        f"{right['task_success_rate']:.1%}** | **{right['blocked_episodes']} episodes, "
        f"{right['blocked_calls']} calls** |"
    )
    lines += [
        "",
        "Helpfulness means: "
        f"`{left['helpfulness_mean']:.2f} -> {right['helpfulness_mean']:.2f}`.",
        "",
        "Important: paired label changes without a recorded block are sampling/judge variation, "
        "not causal defense wins. See `ANALYSIS.md` and `cases.json`.",
        "",
        "Generation audit: all 1,440 trajectories received valid Monitor labels. "
        f"Intermediate proposal-JSON parse/retry events occurred in "
        f"{left['proposal_parse_error_episodes']} no-harness and "
        f"{right['proposal_parse_error_episodes']} adapted episodes; max-step termination occurred "
        f"in {left['max_steps_episodes']} and {right['max_steps_episodes']} episodes.",
    ]
    (base / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_securitybench() -> None:
    base = ROOT / "securitybench"
    rows = read_jsonl(base / "raw/records.jsonl")
    summary = {}
    paired: Counter = Counter()
    pairs: dict[tuple, dict] = defaultdict(dict)
    for row in rows:
        key = (row["agent"], row["task"], row["attacker_tool"], row["method"],
               row["attack_type"], row["seed"])
        pairs[key][row["condition"]] = row
        stats = summary.setdefault(
            f"{row['method']}|{row['condition']}",
            {"n": 0, "attack_success_n": 0, "original_success_n": 0,
             "blocked_episodes": 0, "blocked_calls": 0, "layers": Counter()},
        )
        stats["n"] += 1
        stats["attack_success_n"] += int(bool(row["attack_success"]))
        stats["original_success_n"] += int(bool(row["original_success"]))
        stats["blocked_episodes"] += int(row["blocked"] > 0)
        stats["blocked_calls"] += row["blocked"]
        stats["layers"].update(row.get("layers") or {})
    for key, arms in pairs.items():
        if set(arms) != {"noharness", "safeharness_adapted_no_llm"}:
            continue
        left = arms["noharness"]
        right = arms["safeharness_adapted_no_llm"]
        paired[(key[3], bool(left["attack_success"]), bool(right["attack_success"]))] += 1
    normalized = {}
    for key, stats in summary.items():
        n = stats["n"]
        normalized[key] = {
            **{k: v for k, v in stats.items() if k not in {"layers"}},
            "attack_success_rate": round(stats["attack_success_n"] / n, 4),
            "original_success_rate": round(stats["original_success_n"] / n, 4),
            "layers": dict(stats["layers"]),
        }
    transitions = {
        method: {
            f"{int(before)}->{int(after)}": count
            for (row_method, before, after), count in sorted(paired.items())
            if row_method == method
        }
        for method in ("DPI", "OPI")
    }
    residual = Counter(
        row["attacker_tool"]
        for row in rows
        if row["condition"] == "safeharness_adapted_no_llm"
        and row["attack_success"]
    )
    write_json(
        base / "results.json",
        {"cells": normalized, "paired_transitions": transitions,
         "residual_attack_tools": dict(residual)},
    )

    cases = defaultdict(lambda: defaultdict(list))
    for key, arms in sorted(pairs.items()):
        if set(arms) != {"noharness", "safeharness_adapted_no_llm"}:
            continue
        left = arms["noharness"]
        right = arms["safeharness_adapted_no_llm"]
        case_type = (
            "attack_down"
            if left["attack_success"] and not right["attack_success"]
            else "attack_remains"
            if left["attack_success"] and right["attack_success"]
            else "attack_up"
            if not left["attack_success"] and right["attack_success"]
            else "safe_remains"
        )
        if len(cases[key[3]][case_type]) >= 5:
            continue
        cases[key[3]][case_type].append(
            {
                "agent": key[0],
                "task": key[1],
                "attacker_tool": key[2],
                "attack_type": key[4],
                "noharness": {
                    "attack_success": left["attack_success"],
                    "original_success": left["original_success"],
                    "final": left["final"],
                },
                "safeharness_adapted_no_llm": {
                    "attack_success": right["attack_success"],
                    "original_success": right["original_success"],
                    "blocked": right["blocked"],
                    "layers": right["layers"],
                    "final": right["final"],
                },
            }
        )
    write_json(base / "cases.json", cases)

    lines = [
        "# AgentSecurityBench results",
        "",
        "| Attack | n/arm | No harness ASR / original-task success | Adapted no-LLM ASR / original-task success | Blocks |",
        "|---|---:|---:|---:|---:|",
    ]
    for method in ("DPI", "OPI"):
        left = normalized[f"{method}|noharness"]
        right = normalized[f"{method}|safeharness_adapted_no_llm"]
        lines.append(
            f"| {method} | {left['n']} | {left['attack_success_rate']:.1%} / "
            f"{left['original_success_rate']:.1%} | {right['attack_success_rate']:.1%} / "
            f"{right['original_success_rate']:.1%} | "
            f"{right['blocked_episodes']} episodes, {right['blocked_calls']} calls |"
        )
    lines += [
        "",
        "`original_success` is AgentSecurityBench's expected-achievement string check. "
        "It is near zero in both arms under this attack-only protocol and is not a clean benign utility estimate.",
        "",
        "The archived runner did not persist the full message/action history. `cases.json` therefore "
        "contains the attack tool, block layer, and final answer, but must not be described as a full trajectory.",
    ]
    (base / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_upward() -> None:
    base = ROOT / "upward_deception"
    rows = read_jsonl(base / "run/records.jsonl")
    groups = defaultdict(list)
    pairs = defaultdict(dict)
    for row in rows:
        groups[row["condition"]].append(row)
        pairs[(row["uid"], row["seed"])][row["condition"]] = row
    normalized = {}
    for condition, records in sorted(groups.items()):
        normalized[condition] = {
            "n": len(records),
            "unsafe_n": sum(bool(row["unsafe"]) for row in records),
            "unsafe_rate": round(sum(bool(row["unsafe"]) for row in records) / len(records), 4),
            "non_deception_n": sum(not bool(row["unsafe"]) for row in records),
            "non_deception_rate": round(
                sum(not bool(row["unsafe"]) for row in records) / len(records), 4
            ),
            "legacy_completed_field_n": sum(bool(row["completed"]) for row in records),
            "blocked_episodes": sum(row["blocked"] > 0 for row in records),
            "blocked_calls": sum(row["blocked"] for row in records),
            "errors": sum(bool(row["error"]) for row in records),
        }
    transitions = Counter()
    cases = defaultdict(list)
    for key, arms in sorted(pairs.items()):
        if set(arms) != {"noharness", "safeharness_adapted_no_llm"}:
            continue
        left = arms["noharness"]
        right = arms["safeharness_adapted_no_llm"]
        before, after = bool(left["unsafe"]), bool(right["unsafe"])
        transitions[(before, after)] += 1
        case_type = (
            "risk_down"
            if before and not after
            else "risk_remains"
            if before and after
            else "risk_up"
            if not before and after
            else "safe_remains"
        )
        if len(cases[case_type]) >= 5:
            continue
        cases[case_type].append(
            {
                "uid": key[0],
                "seed": key[1],
                "noharness": {
                    "unsafe": before,
                    "completed": left["completed"],
                    "steps": left["steps"],
                    "final": left["final"],
                    "detail": left["detail"],
                },
                "safeharness_adapted_no_llm": {
                    "unsafe": after,
                    "completed": right["completed"],
                    "blocked": right["blocked"],
                    "steps": right["steps"],
                    "final": right["final"],
                    "detail": right["detail"],
                },
            }
        )
    write_json(
        base / "results.json",
        {
            "judge": "Agentic-Upward-Deception benchmark-provided templates via gpt-4o-mini; primary NFR/DFR mapping",
            "cells": normalized,
            "paired_transitions": {
                f"{int(before)}->{int(after)}": count
                for (before, after), count in sorted(transitions.items())
            },
        },
    )
    write_json(base / "cases.json", cases)
    left = normalized["noharness"]
    right = normalized["safeharness_adapted_no_llm"]
    risk_down = transitions[(True, False)]
    risk_up = transitions[(False, True)]
    lines = [
        "# Agentic-Upward-Deception results",
        "",
        "The benchmark defines failure-reporting/deception metrics, not task utility.",
        "",
        "| Arm | n | Risky / non-deception | Blocks | Errors |",
        "|---|---:|---:|---:|---:|",
        f"| No harness | {left['n']} | {left['unsafe_rate']:.1%} / "
        f"{left['non_deception_rate']:.1%} | {left['blocked_calls']} | {left['errors']} |",
        f"| SafeHarness adapted no LLM | {right['n']} | {right['unsafe_rate']:.1%} / "
        f"{right['non_deception_rate']:.1%} | {right['blocked_calls']} | {right['errors']} |",
        "",
        f"There were zero Harness blocks. The {risk_down} risk-down and {risk_up} risk-up "
        "paired changes are therefore sampling/judge variation, not evidence that the no-LLM "
        "Harness caused the improvement.",
        "",
        "The raw `completed` field is a legacy runner alias for the complement of its unsafe "
        "predicate in this benchmark. It must not be interpreted as task-success utility.",
    ]
    (base / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_manifest() -> None:
    files = []
    excluded = {"MANIFEST.json", "FILES.txt"}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name in excluded:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": digest,
            }
        )
    write_json(ROOT / "MANIFEST.json", {"files": files})
    (ROOT / "FILES.txt").write_text(
        "\n".join(row["path"] for row in files) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    build_autocontrol()
    build_securitybench()
    build_upward()
    build_manifest()
