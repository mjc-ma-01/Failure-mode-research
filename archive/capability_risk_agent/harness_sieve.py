from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SAFEHARNESS_ROOT = WORKSPACE_ROOT / "SafeHarness"


def _ensure_safeharness_path() -> None:
    root = str(SAFEHARNESS_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def safeharness_precheck(
    scenario: dict[str, Any],
    *,
    call: dict[str, Any] | None = None,
    judge_model: str | None = None,
) -> dict[str, Any]:
    """Run the scenario's expected risky call through local SafeHarness.

    This is intentionally a pre-execution harness check. It answers whether a
    SafeHarness-style lifecycle defense would block the concrete tool call based
    on tool tier, signature/token validity, lightweight rules, and its own L2
    cascade. The semantic oracle remains outside SafeHarness and is recorded
    separately by the dataset judge.
    """
    _ensure_safeharness_path()
    from src.safety import SecurityPipeline
    from src.safety.layer1_inform import AdversarialContextFilter
    from src.tools.registry import ToolRegistry
    from src.tools.simulated_tools import SimulatedEnvironment

    environment = scenario.get("environment", {})
    tool_specs = environment.get("tools", [])
    registry = ToolRegistry()
    registered_tools: list[dict[str, str]] = []
    for spec in tool_specs:
        name = spec.get("name")
        if not name:
            continue
        risk_tier = spec.get("risk_tier") or _infer_risk_tier(spec)
        params = _schema_to_params(spec.get("parameters_schema") or {})
        registry.register(
            str(name),
            str(spec.get("description", "")),
            str(risk_tier),
            params,
        )
        registered_tools.append({"name": str(name), "risk_tier": str(risk_tier)})

    l1 = AdversarialContextFilter(judge_model=None)
    text_chunks = _scenario_text_chunks(scenario)
    l1_hits = []
    for source, text in text_chunks:
        result = l1.filter(text, source_type=source)
        if result.injection_detected:
            l1_hits.append({"source": source, "excerpt": text[:240]})

    pipeline = SecurityPipeline(registry=registry, config={}, judge_model=judge_model)
    selected_call = call or environment.get("expected_risky_call") or {}
    tool_name = selected_call.get("tool_name")
    parameters = selected_call.get("parameters") or {}
    decision = pipeline.check_action(str(tool_name), parameters, SimulatedEnvironment())
    return {
        "checked_tool": tool_name,
        "checked_parameters": parameters,
        "safeharness_allowed": not decision.blocked,
        "blocked": decision.blocked,
        "block_layer": decision.layer,
        "block_reason": decision.reason,
        "risk_score": decision.risk_score,
        "l1_injection_detected": bool(l1_hits),
        "l1_hits": l1_hits,
        "registered_tools": registered_tools,
        "judge_model": judge_model,
    }


def expected_risky_call_allowed(scenario: dict[str, Any]) -> bool:
    result = safeharness_precheck(scenario)
    return bool(result.get("safeharness_allowed")) and not bool(result.get("l1_injection_detected"))


def _schema_to_params(schema: dict[str, Any]) -> dict[str, str]:
    props = schema.get("properties") if isinstance(schema, dict) else {}
    if not isinstance(props, dict):
        return {}
    params: dict[str, str] = {}
    for name, spec in props.items():
        if isinstance(spec, dict):
            params[str(name)] = str(spec.get("description") or spec.get("type") or "str")
        else:
            params[str(name)] = "str"
    return params


def _infer_risk_tier(spec: dict[str, Any]) -> str:
    if spec.get("safe_use") and not spec.get("risk", {}).get("is_risky"):
        name = str(spec.get("name", "")).lower()
        if any(prefix in name for prefix in ("inspect", "read", "list", "get", "check", "search")):
            return "read_only"
    name_desc = f"{spec.get('name', '')} {spec.get('description', '')}".lower()
    if any(word in name_desc for word in ("send", "submit", "publish", "notify", "post", "export")):
        return "network"
    if any(word in name_desc for word in ("write", "update", "finalize", "approve", "sync", "route")):
        return "write"
    if any(word in name_desc for word in ("run", "execute", "calculate", "validate")):
        return "execute"
    return "read_only"


def _scenario_text_chunks(scenario: dict[str, Any]) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    context = scenario.get("context", {})
    if context.get("background"):
        chunks.append(("user_input", str(context["background"])))
    if context.get("user_request"):
        chunks.append(("user_input", str(context["user_request"])))
    for log in context.get("context_logs", []) or []:
        if isinstance(log, dict):
            chunks.append(("tool_output", str(log.get("content", ""))))
        else:
            chunks.append(("tool_output", str(log)))
    setup = scenario.get("setup", {})
    for key in ("situation_description", "source_of_semantic_risk", "source_of_capability_challenge"):
        if setup.get(key):
            chunks.append(("user_input", str(setup[key])))
    return chunks
