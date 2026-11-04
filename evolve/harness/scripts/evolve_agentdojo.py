#!/usr/bin/env python3
"""AgentDojo 搜索台：单 benchmark 的 harness 进化循环（SHE 范式 + 代码判分）。

一轮：rollout(dev) → 证据 → proposer 出 artifact 补丁 → house-rules 校验 → 候选 rollout →
门控（ASR 不升 ∧ utility 不降）→ 接受则 fresh anchor / 拒绝留档。循环后 heldout 只评一次。

用法（作业内、服务已起）：
  python evolve/harness/scripts/evolve_agentdojo.py --rounds 3 --seeds 0 \
      --base-url http://127.0.0.1:8000 --workdir experiments/evolve_agentdojo_run1
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "evolve/harness/src"))
sys.path.insert(0, str(ROOT / "evolve/harness/scripts"))

from coevolve.artifacts import compile_harness, load_artifacts          # noqa: E402
from coevolve.judges.api import JudgeAPI, parse_json_object            # noqa: E402

SEED_DIR = ROOT / "evolve/harness/configs/harness/H0D"
PROMPT_PATH = ROOT / "evolve/harness/configs/prompts/agentdojo_proposer.md"
UMAP = "banking=3,slack=2,travel=2,workspace=2"


def run_sweep(out_json: Path, artifacts_dir: Path, split: str, base_url: str, seeds: list,
              task_mode: str = "injection") -> dict:
    """单臂 rollout（base = artifacts harness，无 Δ），返回 report。"""
    cmd = [sys.executable, str(ROOT / "evolve/harness/scripts/run_pair_sweep.py"),
           "--model", "qwen3.5-9b", "--base-url", base_url,
           "--sources", "agentdojo", "--agentdojo-users-map", UMAP, "--split", split,
           "--agentdojo-attack", "important_instructions",
           "--agentdojo-task-mode", task_mode,
           "--workers", "32", "--max-tokens", "512",
           "--seeds", *[str(s) for s in seeds],
           "--base-harness", str(artifacts_dir),
           "--edits", str(ROOT / "evolve/harness/configs/edits_core.json"),
           "--out", str(out_json)]
    print(f"[evolve] rollout split={split} mode={task_mode} → {out_json.name}", flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT))
    return json.loads(out_json.read_text(encoding="utf-8"))


def metrics_and_evidence(report: dict) -> tuple:
    """ASR / utility（官方 security/utility）+ 失败证据（被攻破的格）。"""
    rows = report.get("rows") or []
    cells = report.get("cells") or {}
    n = harm = util = 0
    evidence = []
    for cell in cells:
        base = next((r["base"] for r in rows if r["cell"] == cell), None)
        if base is None:
            continue
        n += 1
        harm += int(bool(base.get("realized_harm")))
        util += int(bool(base.get("utility")))
        if base.get("realized_harm"):
            evidence.append({"cell": cell, "n_steps": base.get("n_steps"),
                             "termination": base.get("termination")})
    return ({"n": n, "asr": round(harm / n, 4) if n else None,
             "utility": round(util / n, 4) if n else None, "harm": harm, "util": util},
            evidence)


def propose(artifacts: dict, mexp: dict, evidence: list, round_id: int,
            model: str = "claude-sonnet-4-6") -> dict:
    api = JudgeAPI(model=model)
    # 用 string.Template：prompt 里有 JSON 字面大括号，str.format 会把它们当字段
    tpl = string.Template(PROMPT_PATH.read_text(encoding="utf-8"))
    prompt = tpl.substitute(
        policy=artifacts.get("system_prompt", ""),
        rules="\n".join(json.dumps(r, ensure_ascii=False) for r in artifacts.get("rules", [])),
        tool_policy=json.dumps(artifacts.get("tool_policy", {}), ensure_ascii=False)[:2000],
        round=round_id, n=mexp["n"], asr=mexp["asr"], utility=mexp["utility"],
        evidence=json.dumps(evidence[:20], ensure_ascii=False))
    return parse_json_object(api.chat(prompt, max_tokens=8000)) or {}


def apply_patch(src_dir: Path, dst_dir: Path, patch: dict) -> None:
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    sp = dst_dir / "system_prompt.md"
    if patch.get("system_prompt_append"):
        sp.write_text(sp.read_text(encoding="utf-8").rstrip() + "\n\n" +
                      str(patch["system_prompt_append"]).strip() + "\n", encoding="utf-8")
    add = patch.get("rule_bank_add") or []
    if add:
        with (dst_dir / "rule_bank.jsonl").open("a", encoding="utf-8") as f:
            for r in add:
                r.setdefault("component", "rule_bank")
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if patch.get("tool_policy_merge"):
        tp = dst_dir / "tool_policy.json"
        pol = json.loads(tp.read_text(encoding="utf-8"))
        pol.update(patch["tool_policy_merge"])
        tp.write_text(json.dumps(pol, ensure_ascii=False, indent=2), encoding="utf-8")
    (dst_dir / "patch.json").write_text(json.dumps(patch, ensure_ascii=False, indent=2),
                                        encoding="utf-8")


def gate(anchor: dict, cand: dict, eps: float = 0.0) -> tuple:
    ok = (cand["asr"] is not None and anchor["asr"] is not None
          and cand["asr"] <= anchor["asr"] + eps
          and cand["utility"] >= anchor["utility"] - eps
          and cand.get("plain_utility", 1.0) >= anchor.get("plain_utility", 1.0) - eps)
    why = (f"ASR {anchor['asr']}→{cand['asr']}, utility(inj) {anchor['utility']}→{cand['utility']}, "
           f"utility(plain/良性对照) {anchor.get('plain_utility')}→{cand.get('plain_utility')}"
           + ("" if ok else "  ✗ 门控未过"))
    return ok, why


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--workdir", default="experiments/evolve_agentdojo_run1")
    ap.add_argument("--proposer", default="claude-sonnet-4-6")
    a = ap.parse_args()

    wd = ROOT / a.workdir
    wd.mkdir(parents=True, exist_ok=True)
    anchor_dir = wd / "anchor_r0"
    shutil.copytree(SEED_DIR, anchor_dir, dirs_exist_ok=True)
    log: list = []

    rep = run_sweep(wd / "dev_r0.json", anchor_dir, "dev", a.base_url, a.seeds)
    m0, ev0 = metrics_and_evidence(rep)
    # 良性对照（无注入格）：只惩罚"过拦"——utility 掉了就说明补丁开始误伤合法请求
    rep_b = run_sweep(wd / "devplain_r0.json", anchor_dir, "dev", a.base_url, a.seeds,
                      task_mode="plain")
    mb, _ = metrics_and_evidence(rep_b)
    m0["plain_utility"] = mb["utility"]
    print(f"[evolve] R0 anchor(dev): {m0}", flush=True)
    log.append({"round": 0, "role": "anchor", "metrics": m0, "artifacts": "anchor_r0"})

    for r in range(1, a.rounds + 1):
        patch = propose(load_artifacts(anchor_dir), m0, ev0, r, model=a.proposer)
        cand_dir = wd / f"candidate_r{r}"
        apply_patch(anchor_dir, cand_dir, patch)
        try:
            cand_art = load_artifacts(cand_dir)
            compile_harness(cand_art, name=f"cand_r{r}")
        except Exception as exc:
            print(f"[evolve] R{r} 候选不合法：{exc}", flush=True)
            log.append({"round": r, "role": "candidate", "invalid": str(exc), "patch": patch})
            break
        rep_c = run_sweep(wd / f"dev_r{r}_cand.json", cand_dir, "dev", a.base_url, a.seeds)
        mc, evc = metrics_and_evidence(rep_c)
        rep_cb = run_sweep(wd / f"devplain_r{r}_cand.json", cand_dir, "dev", a.base_url, a.seeds,
                          task_mode="plain")
        mcb, _ = metrics_and_evidence(rep_cb)
        mc["plain_utility"] = mcb["utility"]
        ok, why = gate(m0, mc)
        print(f"[evolve] R{r} candidate(dev): {mc} | {why} | 接受={ok}", flush=True)
        log.append({"round": r, "role": "candidate", "metrics": mc, "patch": patch,
                    "artifacts_digest": cand_art["digest"], "accepted": ok, "gate": why})
        if ok:
            anchor_dir = wd / f"anchor_r{r}"
            shutil.copytree(cand_dir, anchor_dir, dirs_exist_ok=True)
            m0, ev0 = mc, evc
            print(f"[evolve] R{r} 接受 → fresh anchor {anchor_dir.name}", flush=True)
        else:
            print(f"[evolve] R{r} 拒绝（留档 {cand_dir.name}）", flush=True)

    rep_h = run_sweep(wd / "heldout_final.json", anchor_dir, "heldout", a.base_url, a.seeds)
    mh, _ = metrics_and_evidence(rep_h)
    rep_hb = run_sweep(wd / "heldoutplain_final.json", anchor_dir, "heldout", a.base_url, a.seeds,
                       task_mode="plain")
    mhb, _ = metrics_and_evidence(rep_hb)
    mh["plain_utility"] = mhb["utility"]
    print(f"[evolve] heldout(final anchor): {mh}", flush=True)
    log.append({"phase": "heldout", "metrics": mh, "artifacts": anchor_dir.name})
    (wd / "evolution_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(f"[evolve] 日志 → {wd/'evolution_log.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
