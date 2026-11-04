#!/usr/bin/env python3
"""对比 seed 与进化后 harness 的 artifact 差异（新增/删除/收窄/放宽），输出 markdown。

用法：python harness_diff.py <seed_dir> <best_dir> [--out diff.md]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_rules(d: Path) -> dict:
    p = d / "rule_bank.jsonl"
    out = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[str(r.get("rule_id"))] = r
    return out


def diff_dict(a: dict, b: dict, prefix: str = "") -> list:
    out = []
    for k in sorted(set(a) | set(b)):
        pa = f"{prefix}.{k}" if prefix else k
        if isinstance(a.get(k), dict) and isinstance(b.get(k), dict):
            out += diff_dict(a[k], b[k], pa)
        elif a.get(k) != b.get(k):
            out.append(f"- `{pa}`: `{json.dumps(a.get(k), ensure_ascii=False)[:120]}` → "
                       f"`{json.dumps(b.get(k), ensure_ascii=False)[:120]}`")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seed")
    ap.add_argument("best")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    seed, best = Path(a.seed), Path(a.best)
    sr, br = load_rules(seed), load_rules(best)
    L = ["# harness diff（seed → best）\n"]
    added = [k for k in br if k not in sr]
    removed = [k for k in sr if k not in br]
    changed = [k for k in sr if k in br and sr[k] != br[k]]
    L.append(f"- 规则：新增 {len(added)} / 删除 {len(removed)} / 修改 {len(changed)}")
    for k in added:
        r = br[k]
        L.append(f"  - ➕ `{k}` scope={r.get('scope')} action={r.get('action')} "
                 f"trigger={json.dumps(r.get('trigger'), ensure_ascii=False)[:200]}")
    for k in removed:
        L.append(f"  - ➖ `{k}`（原 action={sr[k].get('action')}）")
    for k in changed:
        L.append(f"  - ✏️ `{k}`: " + json.dumps({"seed": sr[k], "best": br[k]}, ensure_ascii=False)[:500])

    sp_a = (seed / "system_prompt.md").read_text(encoding="utf-8") if (seed / "system_prompt.md").exists() else ""
    sp_b = (best / "system_prompt.md").read_text(encoding="utf-8") if (best / "system_prompt.md").exists() else ""
    L.append("\n## system_prompt\n")
    if sp_a == sp_b:
        L.append("- （无变化）")
    else:
        import difflib
        diff = list(difflib.unified_diff(sp_a.splitlines(), sp_b.splitlines(), "seed", "best", lineterm=""))
        L.append("```diff\n" + "\n".join(diff[:80]) + "\n```")

    ta = json.loads((seed / "tool_policy.json").read_text(encoding="utf-8")) if (seed / "tool_policy.json").exists() else {}
    tb = json.loads((best / "tool_policy.json").read_text(encoding="utf-8")) if (best / "tool_policy.json").exists() else {}
    L.append("\n## tool_policy\n")
    d = diff_dict(ta, tb)
    L.append("\n".join(d) if d else "- （无变化）")

    txt = "\n".join(L) + "\n"
    out = Path(a.out) if a.out else best.parent / "HARNESS_DIFF.md"
    out.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"[diff] 写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
