#!/usr/bin/env python3
"""分层均衡切分（按用户要求：类别均衡 + train/test 不相交）。

AgentHarm：8 个类别 × 3 个原始行为 = 24 训练原始行为（每条 2 个变体）→ 48 有害格；
          其余 20 个原始行为 × 4 变体 = 80 测试有害格；良性孪生同构。
AgentDojo：4 个 suite 各 4 个 dev user + 4 个 held-out user，每个 user × 5 个 injection
          = 每 suite 20 格 → dev 80 格 / held-out 80 格（四类各 25%）。

产物：
  experiments/split_agentharm_balanced/{train,test,benign_train,benign_test}.json
  experiments/split_agentdojo_balanced/{dev,heldout,plain_dev,plain_heldout}.json
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AH = ROOT / "data/AgentHarm/benchmark"
OUT = ROOT / "experiments"


def var_key(b: dict) -> tuple:
    return (bool(b.get("detailed_prompt")), bool(b.get("hint_included")))


def build_ah() -> None:
    H = json.loads((AH / "harmful_behaviors_test_public.json").read_text())["behaviors"]
    B = json.loads((AH / "benign_behaviors_test_public.json").read_text())["behaviors"]
    by_orig = collections.defaultdict(list)
    for b in H:
        by_orig[str(b["id_original"])].append(b)
    by_cat = collections.defaultdict(list)
    for orig, bs in by_orig.items():
        by_cat[bs[0]["category"]].append(orig)
    benign_by = {(str(b["id_original"]), str(b["id"])): b for b in B}

    train_orig, test_orig = [], []
    for cat in sorted(by_cat):
        os_ = sorted(by_cat[cat], key=int)
        train_orig += os_[:3]
        test_orig += os_[3:]

    def uid(kind: str, b: dict) -> str:
        return f"agentharm:{kind}:{b['id_original']}:{b['id']}"

    train, benign_train, test, benign_test = [], [], [], []
    for orig in train_orig:
        vs = sorted(by_orig[orig], key=var_key)           # FF, FT, TF, TT
        pick = vs                                          # 训练覆盖**全部 4 个变体**（否则 ASR 无 headroom）
        for b in pick:
            train.append(uid("harm", b))
            bb = benign_by.get((orig, str(b["id"])))
            if bb:
                benign_train.append(uid("benign", bb))
    for orig in test_orig:
        for b in sorted(by_orig[orig], key=var_key):
            test.append(uid("harm", b))
            bb = benign_by.get((orig, str(b["id"])))
            if bb:
                benign_test.append(uid("benign", bb))

    out = OUT / "split_agentharm_balanced"
    out.mkdir(parents=True, exist_ok=True)
    for name, uids in (("train", train), ("test", test),
                       ("benign_train", benign_train), ("benign_test", benign_test)):
        (out / f"{name}.json").write_text(json.dumps({"name": name, "n": len(uids), "uids": uids},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ah] {name:14s} {len(uids):4d}")
    print(f"[ah] 训练原始行为 {len(train_orig)}（每类 3），测试原始行为 {len(test_orig)}（每类 2~3）")


def build_ad() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "evolve/harness/src"))
    sys.path.insert(0, str(ROOT / "data/AgentDojo/src"))
    from agentdojo.task_suite.load_suites import get_suite

    out = OUT / "split_agentdojo_balanced"
    out.mkdir(parents=True, exist_ok=True)
    dev, held, plain_dev, plain_held = [], [], [], []
    for suite_name in ("banking", "slack", "travel", "workspace"):
        suite = get_suite("v1", suite_name)
        users = sorted(suite.user_tasks)
        inj = sorted(suite.injection_tasks)
        picks = sorted({int(round(i * (len(inj) - 1) / 4)) for i in range(5)})
        while len(picks) < 5:                              # 理论上不会发生；兜底
            picks.append(len(inj) - 1 - len(picks))
            picks = sorted(set(picks))
        inj = [inj[i] for i in picks]
        dev_users, held_users = users[:4], users[4:8]
        for u in dev_users:
            plain_dev.append(f"agentdojo:{suite_name}:{u}:-")
            dev += [f"agentdojo:{suite_name}:{u}:{i}@important_instructions" for i in inj]
        for u in held_users:
            plain_held.append(f"agentdojo:{suite_name}:{u}:-")
            held += [f"agentdojo:{suite_name}:{u}:{i}@important_instructions" for i in inj]
        print(f"[ad] {suite_name:10s} dev_users={len(dev_users)} held_users={len(held_users)} "
              f"inj={len(inj)} cells/split={len(dev_users)*len(inj)}")
    for name, uids in (("dev", dev), ("heldout", held), ("plain_dev", plain_dev),
                       ("plain_heldout", plain_held)):
        (out / f"{name}.json").write_text(json.dumps({"name": name, "n": len(uids), "uids": uids},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ad] {name:14s} {len(uids):4d}")


if __name__ == "__main__":
    build_ah()
    build_ad()
