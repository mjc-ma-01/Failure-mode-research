#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from build_contracts import compile_answers, deterministic_errors


HERE = Path(__file__).resolve().parent


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--contracts",
        type=Path,
        default=HERE / "artifacts" / "contracts",
    )
    args = parser.parse_args()
    changed = 0
    accepted = 0
    for path in sorted(args.contracts.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("accepted"):
            continue
        accepted += 1
        compiled = compile_answers(record["contract"])
        variants = 4 if record["split"] == "train" else 2
        errors = deterministic_errors(record["task"], compiled, variants)
        if errors:
            raise RuntimeError(f"{path}:{errors}")
        before = json.dumps(record["contract"], ensure_ascii=False, sort_keys=True)
        after = json.dumps(compiled, ensure_ascii=False, sort_keys=True)
        record["contract"] = compiled
        record["normalization"] = {
            "compiler": "build_contracts.compile_answers",
            "contract_sha256": hashlib.sha256(after.encode("utf-8")).hexdigest(),
            "semantic_change": (
                "Clarification wording normalized to request the value or "
                "constraint named by missing_field; evidence is unchanged."
            ),
        }
        if before != after:
            changed += 1
        atomic_json(path, record)
    print(
        json.dumps(
            {"accepted": accepted, "changed": changed, "status": "pass"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
