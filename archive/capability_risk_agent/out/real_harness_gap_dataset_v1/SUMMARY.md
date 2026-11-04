# Final Summary: SafeHarness-Resistant Semantic Risk v1

- 场景数: 24
- 风险家族数: 12
- JSON 格式: 标准数组，不再使用 JSONL
- AutoControl Arena 类型: `Capability Shortfall Deception` / `capability_shortfall_semantic`
- 编号策略: 对象使用通用槽位名，不使用具体项目编号
- LLM QC: 24/24 pass
- SafeHarness precheck: 24/24 expected_risky_call 被放行

## 风险定义
- `benign_metric_pressure_distortion`: 2 scenarios
- `contextual_authorization_mismatch`: 2 scenarios
- `downstream_irreversibility_blindspot`: 2 scenarios
- `exception_clause_overgeneralization`: 2 scenarios
- `multi_step_safe_action_composition`: 2 scenarios
- `provenance_laundering`: 2 scenarios
- `relational_privacy_inference`: 2 scenarios
- `representational_harm_by_normalization`: 2 scenarios
- `semantic_scope_fanout`: 2 scenarios
- `shallow_assurance_overtrust`: 2 scenarios
- `tacit_organizational_redlines`: 2 scenarios
- `temporal_validity_decay`: 2 scenarios

## 主要文件
- `scenarios.json`
- `DATA_REPORT_CN.md`
- `summary.json`
- `reference_expected_risky_trajectories.json`
- `reference_expected_risky_judgments.json`
- `reference_expected_safe_trajectories.json`
- `reference_expected_safe_judgments.json`
- `one_step_trajectories.json`
- `one_step_judgments.json`
- `rejected.json`
