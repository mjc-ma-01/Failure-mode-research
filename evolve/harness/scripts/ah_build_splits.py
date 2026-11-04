#!/usr/bin/env python3
"""AgentHarm 的 train/test 切分（SHE 式：进化只用 train，留出集按**攻击强度**与**未见行为**两轴）。

产物（experiments/split_agentharm/）：
  train30.json       30 个原始行为 × 1 个变体（detailed=True, hint=True，最强提示）→ 进化用
  test_variants.json 同 30 个行为 × 其余 3 个变体（TF/FT/FF）→ 攻击强度泛化
  test_unseen.json   其余 14 个行为 × 全部 4 个变体 → 未见行为泛化
  benign_train.json  上述 30 个行为的 **benign 孪生**（同 id_original/id）→ 效用轴（防过拦）
  benign_test.json   其余 14 个行为的 benign 孪生
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AH = ROOT / "data/AgentHarm/benchmark"
OUT = ROOT / "experiments/split_agentharm"


def load(name: str) -> list:
    return json.loads((AH / name).read_text(encoding="utf-8"))["behaviors"]


def var_key(b: dict) -> tuple:
    return (bool(b.get("detailed_prompt")), bool(b.get("hint_included")))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    H, B = load("harmful_behaviors_test_public.json"), load("benign_behaviors_test_public.json")
    h_by_orig = defaultdict(list)
    for b in H:
        h_by_orig[str(b["id_original"])].append(b)
    originals = sorted(h_by_orig, key=int)
    train_orig, test_orig = originals[:30], originals[30:]
    benign_by = {(str(b["id_original"]), str(b["id"])): b for b in B}

    def uid(kind: str, b: dict) -> str:
        return f"agentharm:{kind}:{b['id_original']}:{b['id']}"

    train, test_var, test_unseen, ben_train, ben_test = [], [], [], [], []
    for orig in train_orig:
        vs = sorted(h_by_orig[orig], key=lambda b: (not var_key(b)[0], not var_key(b)[1], b["id"]))
        train.append(uid("harm", vs[0]))                     # TT（最强）
        for b in vs[1:]:
            test_var.append(uid("harm", b))
        for b in vs:
            bb = benign_by.get((orig, str(b["id"])))
            if bb:
                ben_train.append(uid("benign", bb))
    for orig in test_orig:
        for b in h_by_orig[orig]:
            test_unseen.append(uid("harm", b))
            bb = benign_by.get((orig, str(b["id"])))
            if bb:
                ben_test.append(uid("benign", bb))

    for name, uids in (("train30", train), ("test_variants", test_var), ("test_unseen", test_unseen),
                       ("benign_train", ben_train), ("benign_test", ben_test)):
        p = OUT / f"{name}.json"
        p.write_text(json.dumps({"name": name, "n": len(uids), "uids": uids},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{name:<14} {len(uids):>4} 格 → {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
