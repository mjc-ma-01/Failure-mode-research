from __future__ import annotations

import ast
import hashlib
import json
import unittest
from pathlib import Path


EXPERIMENT = Path(__file__).resolve().parents[1]


class HarnessSelfContainedTest(unittest.TestCase):
    def test_autocontrol_registry_is_frozen_285_record_copy(self) -> None:
        path = EXPERIMENT / "autocontrol" / "tool_tier_registry.json"
        records = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(records), 285)
        self.assertTrue(all({"name", "effect", "tier"} <= set(row) for row in records))
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "9198ac3c18001858079a05c04b3c4b2ae57ab40e4290238aece9962d0b0c0ba0",
        )

    def test_runtime_code_does_not_import_sft_experiment(self) -> None:
        runtime_files = [
            EXPERIMENT / "autocontrol" / "core_eval.py",
            EXPERIMENT / "autocontrol" / "run_eval_react.py",
            EXPERIMENT / "autocontrol" / "score_monitor_local.py",
            EXPERIMENT / "securitybench" / "canonical_eval.py",
            EXPERIMENT / "securitybench" / "run_eval_react.py",
            EXPERIMENT / "securitybench" / "run_eval_react_local.py",
            EXPERIMENT / "shared" / "react_protocol.py",
            EXPERIMENT / "shared" / "safeharness_no_llm.py",
        ]
        for path in runtime_files:
            self.assertNotIn("model_vs_harness_sft", path.read_text(encoding="utf-8"))

    def test_securitybench_tokens_are_not_issued_for_full_pending_queue(self) -> None:
        path = EXPERIMENT / "securitybench" / "run_eval_react_local.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        direct_pending_episode_comprehensions = []
        sliced_pending_episode_comprehensions = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ListComp):
                continue
            if not isinstance(node.elt, ast.Call):
                continue
            if not isinstance(node.elt.func, ast.Name) or node.elt.func.id != "Episode":
                continue
            for generator in node.generators:
                if isinstance(generator.iter, ast.Name) and generator.iter.id == "pending":
                    direct_pending_episode_comprehensions.append(node.lineno)
                if (
                    isinstance(generator.iter, ast.Subscript)
                    and isinstance(generator.iter.value, ast.Name)
                    and generator.iter.value.id == "pending"
                ):
                    sliced_pending_episode_comprehensions.append(node.lineno)
        self.assertEqual(direct_pending_episode_comprehensions, [])
        self.assertTrue(sliced_pending_episode_comprehensions)

    def test_securitybench_inputs_are_local_or_benchmark_data(self) -> None:
        self.assertTrue(
            (EXPERIMENT / "securitybench" / "asb_tier_table_5agents_principled.json").is_file()
        )
        base = EXPERIMENT / "securitybench" / "raw" / "base_trace_panel.jsonl"
        self.assertEqual(
            hashlib.sha256(base.read_bytes()).hexdigest(),
            "b4d8986e6e76bde9669401cb6f6bba9b95fcafb1be25a5bb0605a0e0c696c398",
        )


if __name__ == "__main__":
    unittest.main()
