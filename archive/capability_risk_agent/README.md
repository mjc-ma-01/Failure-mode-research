# Capability Risk Agent

This package implements a Shadow-Self/IMPRESS-style data construction pipeline
for **SafeHarness-resistant semantic risks**.

The target data is not jailbreak, prompt injection, malicious user misuse, tool
tampering, or a compromised system. The user task and goal are benign. The
risky action is a normal-looking tool call that a lifecycle harness such as
SafeHarness is likely to allow, while the actual violation depends on
high-dimensional scenario semantics: provenance, authorization, entity binding,
audience scope, temporal state, workflow preconditions, shallow validation, or
multi-step postconditions.

## Thesis

External harnesses are strong against syntactic, tier-level, and known
threat-model risks, but they can miss semantic risks where:

- the tool is legitimate;
- the arguments contain no obvious secret, destructive command, or injection;
- every single step looks routine;
- the violation is only visible after joining several context facts.

The dataset therefore uses SafeHarness itself as a sieve: a scenario is retained
only if its `expected_risky_call` passes local SafeHarness precheck while the
scenario oracle still marks the call as semantically unsafe.

## Pipeline

1. `setup`: sample a harness blindspot and semantic risk, then create role,
   benign goal, safe path, risky path, and why SafeHarness should miss it.
2. `contextualization`: expand into realistic background plus logs/messages/
   policies/records. The risk is factual but never directly requested.
3. `environment`: create JSON mock tools, memory, success criteria, risk
   criteria, `expected_safe_call`, `expected_risky_call`, and a harness
   blindspot oracle.
4. `quality_control`: judge realism, benign goal, no misuse trigger, semantic
   risk, safe alternative, harness blindspot fit, risk observability, tool
   quality, and high-dimensionality.
5. `safeharness_precheck`: register generated tools with local SafeHarness and
   keep only scenarios where `expected_risky_call` is allowed.
6. `run`: roll out the target model, defaulting to `deepseek-v4-flash`, with
   SafeHarness protecting every proposed tool call.
7. `judge`: label execution success, risk induced, risk considered,
   `harness_escaped`, semantic failure, and final label.

## Quick Start

Offline smoke test:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m capability_risk_agent.cli generate \
  --dry-run \
  --pipeline harness-gap \
  --n-per-cell 1 \
  --blindspots provenance_certification_gap,shallow_validator_overtrust \
  --semantic-risks false_verification,unapproved_workflow_finalization \
  --out capability_risk_agent/out/harness_gap_scenarios.json

PYTHONDONTWRITEBYTECODE=1 python3 -m capability_risk_agent.cli summarize \
  --input capability_risk_agent/out/harness_gap_scenarios.json
```

Use an OpenAI-compatible NewAPI endpoint:

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="http://35.220.164.252:3888"

python3 -m capability_risk_agent.cli generate \
  --pipeline harness-gap \
  --model deepseek-v4-flash \
  --n-per-cell 2 \
  --blindspots all \
  --semantic-risks false_verification,wrong_entity_action,contextual_privacy_leak \
  --out capability_risk_agent/out/harness_gap_scenarios.json

python3 -m capability_risk_agent.cli run \
  --scenarios capability_risk_agent/out/harness_gap_scenarios.json \
  --model deepseek-v4-flash \
  --security-mode safeharness \
  --out capability_risk_agent/out/harness_gap_trajectories.json

python3 -m capability_risk_agent.cli judge \
  --scenarios capability_risk_agent/out/harness_gap_scenarios.json \
  --trajectories capability_risk_agent/out/harness_gap_trajectories.json \
  --model deepseek-v4-flash \
  --out capability_risk_agent/out/harness_gap_judgments.json
```

For offline debugging, `judge --heuristic` labels risk from mock tool risk flags.

## Main Labels

Each scenario includes:

- `harness_blindspot`: why a SafeHarness-style defense can miss it.
- `semantic_risk`: the concrete risk family.
- `expected_safe_call`: the safe action path.
- `expected_risky_call`: the call that should pass SafeHarness but violate the
  semantic oracle.
- `safeharness_precheck`: local SafeHarness decision on `expected_risky_call`.
- `labels`: benign-goal and no-misuse/no-injection/no-tool-compromise flags.

Each judgment includes:

- `execution_success`
- `risk_induced`
- `risk_considered`
- `harness_escaped`
- `semantic_failure_observed`
- `label`, especially `harness_escaped_semantic_risk`
