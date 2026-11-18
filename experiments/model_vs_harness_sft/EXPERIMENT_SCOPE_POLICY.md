# Active experiment scope policy

User directive, frozen on 2026-11-13:

1. All subsequent AutoControl model-vs-harness experiments exclude
   `Capability Misuse` from training, evaluation, aggregation, and claims.
2. AutoControl SFT uses W1 visible policy-choice supervision only.
3. W2 visible state-calibration, synthetic tool-denial, `partial`, and `failed`
   targets are excluded from training and the main comparison.
4. Historical W2/mixed models and results may be cited only as previous
   diagnostics; they must not be merged into the active experiment.
5. The active comparable arms are Base, W1-only SFT, and Base + SafeHarness
   adapted no-LLM. SFT+Harness is not required.

The canonical implementation and setting are under
`autocontrol_w1_only/`. If another script or document conflicts with this
policy, this file and the user directive take precedence for new experiments.
