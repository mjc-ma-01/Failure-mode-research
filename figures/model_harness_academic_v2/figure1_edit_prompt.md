# Final Directed Revision

Review corrections: connected evidence provenance, paired artifacts rather than a false update arrow, conditional retries, and development-versus-held-out evaluation separation.

```text
Edit the supplied English scientific Figure 1 with a strictly targeted final correction. Preserve the current four-panel narrative, lettering quality, controlled hand-inked scientific comic style, blue/coral/lavender/mint semantics, same refund example, all correct text, and all successful icon illustrations. Do not revert to the previous Chinese flowchart.

Make ONLY the following carefully scoped changes:

1. CANVAS AND MARGINS. Change the overall canvas from the current 3:2 to a 4:3 LANDSCAPE scientific page, ideally 2048 x 1536. Do not preserve the reference aspect ratio. Extend the pure-white canvas and modestly reflow/reposition the panel groups if necessary; never stretch letters or icons. Give the ENTIRE figure a generous continuous pure-white margin of approximately 4% of canvas width on all edges, including above panel (a), left of the title, right of panel (d), and below the legend. No panel or text may approach or touch the outside boundary. The bottom legend and fixed-foundation note must remain fully inside these margins.

2. CONNECT THE INCIDENT TO ITS LOG. The current "Log and verify" line in the upper-left gutter starts in empty white space rather than at panel (a). Connect its source precisely to the lower-left boundary of panel (a), route through the reserved upper white gutter without crossing the title or subtitle, and terminate with an arrowhead at the top of panel (c)'s shared episode record. Keep its existing label. No floating disconnected start. Do not let it intersect another connector.

3. SHOW A PAIR, NOT A CAUSAL WEIGHT UPDATE. At the bottom-right of panel (b), in the small artifact labeled "New model + new harness", replace the arrow between the orange protocol-file icon and blue weight-matrix icon with a clearly drawn neutral PLUS SIGN. This represents two jointly evaluated artifacts, NOT code directly updating weights. Preserve the label and the green "Evaluate pair" arrow going to panel (d).

4. MAKE THE PROTOCOL PATCH CONDITIONAL. In panel (b)'s "Propose edits" code diff, the final added line must read:
"+ if failed: retry(id)"
instead of the current unconditional "+ retry(id)".
Make the code window wide enough to keep this line readable without spilling outside it.
Keep the preceding lines "- retry()", "+ bind_id(id)", and "+ check_status(id)".
In the small patch summary underneath, preserve:
"+ bind operation ID"
"+ query prior status"
and replace the last line with:
"+ confirmed failure: same-ID retry"
Use three readable lines, slightly enlarge the patch note within available whitespace if needed.
These are schematic protocol steps, not a complete executable code listing. Do not remove the status query or imply that success should trigger another refund.

5. SEPARATE DEVELOPMENT SELECTION FROM HELD-OUT REPORTING. At the bottom of panel (d), replace "Accept or roll back" with these TWO short exact lines:
"Dev: accept / roll back"
"Held-out: report only"
Keep the evaluation checklist and target behavior above intact. Ensure adequate vertical spacing from the lower panel border. No held-out test outcomes should be shown feeding version selection.

Everything else should remain semantically and visually the same. In particular, retain:
- "Observed: timeout" versus "Hidden: already refunded".
- "Actor frozen" for protocol evolution and "Harness frozen" for actor training.
- "Task variants -> Fresh rollouts -> Independent reward -> GRPO".
- The independently verified blocked unsafe proposal with "Unsafe proposal: YES" and "Realized harm: NO".
- The version-pairing matrix, target refund behavior, no invented performance measurements.
- A single dashed bottom feedback route.
All visible text remains English. Maintain legibility, balanced panels, non-crossing arrows, pure white background, subtle linework, and restrained pale colors. Do not add new modules, new equations, Chinese text, logos, fabricated benchmark numbers, or decorative clutter.
```
