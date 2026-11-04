# Figure 1: Learning Agent Safety through Model-Harness Co-evolution

**English caption.** A single verified failure supplies evidence for two complementary updates. (a) A benign refund request becomes unsafe when an agent treats a timeout as proof of failure and initiates a second independent refund. (c) The shared episode record separates the actor's original proposal from harness intervention and the realized outcome: successful interception can prevent harm without correcting the actor's decision. (b) With the actor frozen, an editor proposes executable protocol changes that are selected through sandbox and regression tests. With the selected harness frozen, reconstructed task variants generate fresh on-policy trajectories; independent utility and risk feedback then update actor weights through GRPO. Old records inform diagnosis and task construction rather than directly replacing new rollouts. (d) Joint evaluation compares model-harness combinations. Development evaluation governs acceptance or rollback; held-out transfer to new tasks, tools, and harnesses is reported separately without selecting versions on those test results. New training experience restarts the cycle.

**图意。** 同一次经过核验的失败，同时用于改执行协议和训练模型判断。两条路径共用事故证据，但更新方法与产物不同。外部成功拦截了危险提交，不代表模型已经学会安全决策。评测面板展示需要验证的问题，不表示已经取得迁移收益或安全保证。

## Interpretation Boundaries

- This is a proposed framework illustration, not a report of trained models or measured improvements.
- Actor observations and evaluator-only environment truth are distinct. The actor must acquire missing evidence through legitimate tools.
- Dangerous proposals are checked independently; blocking alone is not proof of danger, and safe retries or necessary checks are not classified as failures.
- The execution substrate must support the idempotency guarantees illustrated. Otherwise the protocol must verify, pause, or escalate rather than assume safe execution.
- Permissions, trusted credential/state sources, and evaluation rules remain outside the editor's mutable protocol space.
- The pairwise evaluation matrix compares version combinations; its cells are not experimental scores.

## Style Adaptation

The supplied TRACE-Agent prompt was used for its 4:3 two-level composition, four scientific panels, restrained hand-inked linework, pale blue/coral/lavender palette, and recurring visual example. Its unrelated architecture, memory system, and rollback modules were not adopted.

The previous Chinese figure is preserved in the sibling model_harness_shared_failure_20260906 directory. The English figure is a new version rather than an overwrite.
