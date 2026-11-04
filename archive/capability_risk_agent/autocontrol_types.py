from __future__ import annotations

from typing import Any


AUTOCONTROL_RISK_CATEGORY = "Capability Shortfall Deception"
AUTOCONTROL_SCENARIO_TYPE = "capability_shortfall_semantic"


def autocontrol_metadata(
    *,
    family: str | None = None,
    capability_gap: str | None = None,
    semantic_risk: str | None = None,
    stress_level: int = 0,
    temptation_level: int = 1,
    env_complexity_level: int = 1,
) -> dict[str, Any]:
    return {
        "risk_category": AUTOCONTROL_RISK_CATEGORY,
        "scenario_type": AUTOCONTROL_SCENARIO_TYPE,
        "family": family or semantic_risk or capability_gap or "semantic_risk",
        "capability_gap": capability_gap,
        "semantic_risk": semantic_risk,
        "stress_level": stress_level,
        "temptation_level": temptation_level,
        "env_complexity_level": env_complexity_level,
    }
