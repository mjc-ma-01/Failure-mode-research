# AgentSecurityBench reproduction runner

This runner covers both canonical attack methods, **DPI and OPI**, rather than
only AutoControl. It reads the public benchmark checkout from
`data/AgentSecurityBench`, uses the frozen offline tier table in `../config/`,
and compares:

- `noharness`
- `safeharness_adapted_no_llm`

The harness arm uses no runtime judge LLM. The agent model still needs an
OpenAI-compatible endpoint.

Validate the canonical 1,200-cell plan without making API calls:

```bash
python experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/code/run_eval.py \
  --out /tmp/securitybench-reproduction.jsonl \
  --plan-only
```

Run it:

```bash
export OPENAI_BASE_URL=https://your-endpoint.example/v1
export OPENAI_API_KEY=your-local-secret
python experiments/noharness_vs_safeharness_adapted_no_llm/securitybench/code/run_eval.py \
  --out /tmp/securitybench-reproduction.jsonl
```

Do not overwrite the frozen canonical files under `../raw/`.
