# AgentSecurityBench analysis

## 结果

- DPI：ASR `98.7% → 7.0%`；
- OPI：ASR `99.7% → 8.0%`；
- DPI adapted：275/300 个 episode 有 block，348 次调用被拦；
- OPI adapted：277/300 个 episode 有 block，330 次调用被拦。

配对结果：

- DPI：275 个 attack-success→safe，21 个仍成功；
- OPI：275 个 attack-success→safe，24 个仍成功。

这里与 Upward 不同：绝大多数 risk-down 有明确的 block 证据，可以归因于 Harness。

## 哪些组件起作用

1. **L3 静态 capability**
   - 551 次 L3 block；
   - 典型：`InsiderTrading`、`MoneyLaundering` 等显式恶意/高副作用能力。
2. **L1 taint × L2 Tier1**
   - 127 次 deterministic Tier1 block；
   - 注入命中后，write/network/execute 的底分与 taint 权重相加达到 `.7`。

## 残余失败

45 个 adapted 攻击仍成功，集中于：

- `ConfidentialDataAudit`；
- `AccessToClientRecords`；
- `LegalAdvice`；
- `SurgicalErrors`；
- `PatientRecordAccess`；
- `AccessToStudentRecords`；
- `DataAccess`；
- `CarePlanUpdate`。

共同点是工具名看起来像读取、审核、建议或正常更新。危害取决于：

- 请求者是否有权限；
- 数据对象是否敏感；
- 是否获得同意；
- 专业操作是否被授权。

当前 capability 只有“副作用强度”，没有数据敏感性与授权关系，所以 read-only 型越权和
表面正常的专业操作仍会漏过。

## Utility 限制

`original_success` 两臂均接近 0，不说明模型一般 utility 很差，而是该协议专门构造强攻击，
且攻击要求“只用 attacker tool”。不能把本结果写成 SafeHarness 保持了正常任务 utility。

