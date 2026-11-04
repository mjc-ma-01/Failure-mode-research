# Agentic-Upward-Deception reproduction runner

This project-side runner compares `noharness` with
`safeharness_adapted_no_llm` on the frozen 32-task list. It uses the same
deterministic SafeHarness pipeline as AgentSecurityBench and evaluates outcomes
with the benchmark-provided templates under `../config/official_judge_templates/`.

Validate the 64-episode plan without API calls:

```bash
python experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/code/run_eval.py \
  --out-dir /tmp/upward-deception-reproduction \
  --plan-only
```

Run it:

```bash
export OPENAI_BASE_URL=https://your-endpoint.example/v1
export OPENAI_API_KEY=your-local-secret
python experiments/noharness_vs_safeharness_adapted_no_llm/upward_deception/code/run_eval.py \
  --out-dir /tmp/upward-deception-reproduction
```

The outcome judge uses `gpt-4o-mini` by default. That offline outcome judge is
separate from the harness: the harness itself makes no additional LLM calls.
