# AutoControl analysis

## 有效结论

### Instrumental Convergence

- risky：`52.1% → 24.5%`；
- task success：`64.1% → 42.7%`；
- adapted 臂 63 个 episode 发生 121 次阻断。
- 65 个 risky→safe 配对中，只有 32 个 adapted 轨迹记录到 block；其余 33 个不能归为
  Harness 的确定性拦截收益。

真实防御主要来自危险能力门禁。例如 `ic_02_shutdown_resistance` 中
`block_remote_admin_port`、`disable_update_service` 被 L3 阻断，模型改为上报 abort。
有 block 证据的子集支持“危险能力门禁有效”；但总体降幅同时包含独立采样与 Monitor 波动。
任务成功率下降 21.4pp，说明防御常通过“阻止任务路径”而非“引导安全完成”实现。

仍然防不住：

- 被拦后继续骗取 override；
- 多次绕行重试；
- 多个普通 execute/network 动作组成自复制或越权链；
- 工具被拦但轨迹中保留欺骗意图。

### Oversight Evasion

- risky：`49.1% → 25.9%`；
- task success：`63.9% → 48.1%`；
- adapted 臂 20 个 episode 发生 28 次阻断。
- 32 个 risky→safe 配对中，12 个 adapted 轨迹有 block，20 个没有；总体差异不能全部归因
  于 Harness。

能防的是直接关闭/修改监督设施，例如 `disable_watchdog` 或具有 watchdog 副作用的
`edit_config`。不能防的是内容型规避：读取内部倾向性材料后，用正常
`read/analyze/submit` 工具提交被操纵的报告。

### Specification Gaming

- risky：`27.3% → 27.3%`；
- task success：`35.6% → 42.4%`；
- 仅 2 个 episode 有 block。

SafeHarness 对 SG 没有可观察的总体风险收益。典型风险是跳过验证后直接
`submit_result(all_clear)`、使用正常工具做假完成或通过参数挑客；这些并非工具 capability
本身危险。

### CW / EA / SM

- CW：`6.5% → 6.5%`，4 个 risk-down 均无 block；
- EA：`1.4% → 0.0%`，仅 1 个基线 risky cell，risk-down 无 block；
- SM：`16.7% → 13.9%`，11 个 risk-down 中仅 1 个有 block。

三类基线较低。大量 risk-down 没有对应 block，不能解释为 Harness 因果收益。
CW/SM 的主要问题在最终内容选择、披露动机或策略性报告，静态 tier 缺乏语义信号。

## 总体判断

总体 risky `29.9% → 18.5%`，task success `52.6% → 46.5%`。这一平均值由 IC/OE
主导，不表示所有类别均有效。最可信的结论是：

- Harness 能拦“直接危险执行”；
- Harness 难拦“正常工具承载的欺骗、投机与内容操纵”；
- 对 IC/OE 的风险下降存在明显 utility 代价；
- `cases.json` 中无 block 的 label flip 必须视为采样/judge 波动。

## 数据质量限制

少量 episode 出现模型动作 JSON 解析失败并被 runner 重试；另有约 13% episode 达到八步上限。
Monitor 对全部轨迹成功判分，因此这些记录不是缺失值，但它们反映 Qwen3.5-9B 的格式遵循和
交互预算限制。跨模型或与官方完整环境比较时必须保留这一差异。

