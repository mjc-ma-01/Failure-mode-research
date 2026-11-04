# evolve/policy

模型侧更新（第二部分），**按计划先留空**，等 harness 侧链路跑通后再整理。

## 这里将来放什么

- 训练数据构造：把 verified 的失败证据转成任务重建引用；SFT 用示范轨迹，RL 用当前权重重新采样。
- 训练入口：harness-use SFT -> harness-augmented GRPO（框架与阶段划分待定）。
- checkpoint 管理：训练前后权重、版本回执、可回滚点。
- 与 harness 侧的接口：harness 版本随 training manifest 一起固定，避免把"改了协议"当成"改了模型"。

## 需要先定的事

- [ ] 用哪几个 bench 的哪一部分做训练，哪些只做评测（不能拿测试集训练）。
- [ ] SFT 数据从哪来：模型自己通过 harness 的轨迹，还是人工/规则示范？
- [ ] Qwen3-8B 的本地 ckpt 路径与 revision（旧工程用的是 Qwen3-4B，本次要求 8B）。
- [ ] 训练算力与框架：是否复用旧工程的 verl 适配与集群提交脚本。

以上问题定了再动手写代码。
