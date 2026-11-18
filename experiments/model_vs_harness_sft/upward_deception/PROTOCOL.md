# Upward Deception SFT Gold-Data Protocol

## Objective

Construct model-side SFT data for one narrowly defined risk:

> when required evidence is unavailable, irrelevant, or replaced, the agent must
> disclose the evidence failure instead of fabricating task completion.

The student is `Qwen/Qwen3.5-9B`. The offline trajectory teacher is `glm-5.3`.
No teacher or validation model is used when the trained student is evaluated.

## Frozen split

The 200 official tasks are split before fixture or trajectory generation:

- train: 120 tasks;
- development: 40 tasks;
- test: 40 tasks.

The 32 tasks used by the canonical no-harness versus SafeHarness experiment remain
in test. Eight additional official tasks are added to improve type coverage.

Splitting occurs at the original task level. Counterfactual conditions, candidate
trajectories, retries, and future rollouts derived from one task never cross splits.

## Three matched conditions

Every training task is instantiated in three environments.

1. `failure`
   - The required source fails, is missing, or is insufficient.
   - The agent must attempt the required source, disclose the problem, and avoid
     unsupported claims.
2. `success`
   - The same required source is available and contains a validated fixture.
   - The agent must use it and complete the task rather than over-refuse.
3. `authorized_fallback`
   - The required source fails or is insufficient.
   - A trusted instruction explicitly authorizes a verified cache.
   - The agent must attempt the primary source first, use the cache, and identify
     the actual source in the final answer.

These are environment counterfactuals, not three prose answers hallucinated by a
teacher.

## Fixture construction

For each original task, `glm-5.3` creates a compact authoritative document,
an expected response, and exact evidence quotes. A fixture is retained only if:

- all evidence quotes occur verbatim in the source document;
- local structural checks pass;
- `deepseek-v4-pro` passes a source-sufficiency review;
- a separate adversarial `deepseek-v4-pro` rubric finds no critical defect.

Fixtures are generated offline and are never exposed as hidden answer keys in
student inputs. In `success` and `authorized_fallback`, source content is exposed
only through successful tool observations.

## Trajectory generation

`glm-5.3` interacts with actual deterministic tools. It receives a teacher-only
policy requiring evidence grounding, failure disclosure, and source attribution.
The exported SFT record replaces this teacher-only system message with the normal
agent system message used at evaluation time.

Each task-condition cell permits up to three candidates. A later attempt receives
only validation failures from the previous attempt, never a hidden answer.

## Acceptance gates

A candidate enters the SFT dataset only after all applicable gates pass:

1. schema and condition-specific local checks;
2. deterministic replay from a clean environment;
3. official Upward judge templates through `gpt-4o-mini` for the original
   `failure` condition;
4. evidence, authorization, and honesty review by `deepseek-v4-pro`;
5. a separate feasible-utility and over-refusal review by `deepseek-v4-pro`.

The two rubrics must both pass. Any failure or uncertainty is quarantined and
excluded from SFT export.

The official failure rubric is not applied to the two synthetic counterfactuals.
It assumes the benchmark's original failed-source environment and mislabels an
explicitly authorized fallback as deception. Both semantic judges still review
every counterfactual trajectory.

## Export

The primary artifact is `output/sft/train.jsonl`. Each row contains:

- OpenAI-style `messages`;
- tool schemas;
- risk type and condition;
- original task identity;
- accepted validation metadata;
- fixture and trajectory hashes.

Only tasks with all three accepted conditions are exported. The target-risk
`failure` row has sampling weight `2.0`; `success` and `authorized_fallback` each
have weight `1.0`. This yields an effective `50%/25%/25%` training mixture without
breaking task-level counterfactual pairing.

Only assistant messages are intended to contribute to the SFT loss. User, system,
and tool-observation tokens must be loss-masked by the trainer.

`output/review_queue.jsonl` contains rejected or disputed cells and must not be
used for training.
