# Figure 1: Learning Agent Safety

基于用户提供的四面板科学插画风格重构；保留 model-harness 共同学习的方法内容，不引入参考模板中的 TRACE-Agent 架构。

使用技能：academic-figure-prompt。方式：内置 image_gen，参考上一版图做全局重绘。图中文字：英文。构图：4:3。

```text
Create a completely redesigned, publication-ready scientific overview illustration for Figure 1 of an agent-safety research paper. Use the attached previous figure ONLY as a reference for the scientific subject and refund example. Do NOT preserve its horizontal PowerPoint layout, Chinese typography, plain rectangular flowchart appearance, or large explanatory sentence. This is a substantial visual redesign with ALL text in English.

SCIENTIFIC SUBJECT
The subject is MODEL–HARNESS SAFETY CO-EVOLUTION, not TRACE-Agent. The research insight is: the same independently verified failure episode can improve executable safety protocols and the actor's own decision-making, through two distinct update mechanisms. A blocked unsafe action must remain a learning signal even when the harness prevents realized harm. The harness is changed by tested code/configuration edits with the actor frozen; the actor is subsequently changed by on-policy RL on freshly sampled trajectories with the accepted harness frozen. This is a proposed method diagram, not empirical results.

RUNNING EXAMPLE
A benign user asks for a refund ONCE. The first API operation succeeds, but the response times out. The model observes a timeout, assumes failure, and issues a SECOND INDEPENDENT refund, causing a duplicate. "Timeout" is observed; "first refund succeeded" is hidden environment truth used by the evaluator, not privileged information fed to the acting model. The actor can query transaction status. Subsequent protocol evolution binds the business operation to a trusted idempotency identifier and verifies status before retry. The actor learns to check status and select a safe continuation. Do not depict malicious users, prompt injection, or an attacker.

VISUAL LANGUAGE
A polished digitally hand-inked scientific comic infographic suitable for a serious NeurIPS Figure 1. Regular geometry, hand-drawn linework. Precise dependency arrows and expressive small scientific illustrations, not a corporate slide with text-only boxes. Pure white canvas, subtle marker-like contours, compact transaction receipts, tool console, evidence sheets, code-diff sheet, weight matrix, sandbox test checklist, and paired-checkpoint evaluation grid. Detailed but readable, no useless decoration.

CANVAS AND SPATIAL COMPOSITION
Landscape 4:3 aspect ratio, approximately 2048 x 1536 pixels or higher available resolution. Absolutely pure white outer background #FFFFFF. Reserve at least 45-55 pixels of whitespace on every outer edge at the requested scale. No cropped labels.
Two-level four-panel composition:
Upper-left unboxed title area, about 21% width and 25% height.
Upper-middle/right panel (a), about 73% width and 25% height.
Lower-left panel (c), about 20% width and 61% height.
Dominant lower-center panel (b), about 54% width and 61% height.
Lower-right panel (d), about 20% width and 61% height.
Leave consistent 30-40 pixel white gutters. Keep the right evaluation panel wide enough to read its checklists and version grid. Center panel must visibly dominate.
A dedicated white corridor between the upper and lower regions carries the incident-to-record arrow. A dedicated bottom corridor carries one dashed return arrow. No decorative crowding around connectors.

PALETTE
Structural blue #0969C7 for model learning and dominant panel boundaries.
Warm coral #F27A5B for risk and executable protocol changes.
Muted lavender #9387B2 only for the shared-evidence border.
Charcoal #2E3035 for normal labels.
Mint #72CEA4 and darker green for verification.
Cyan #74CAD8 and mustard #E2B74B as tiny semantic accents only.
Pale fills: #FFF1ED, #EEF6FE, #F4F1FA, #EFFAF7 and white.
At least 80% of image area white or extremely pale. Colored strokes and small accents, not saturated full-area fills. No dominant violet, dark blue theme, beige background, gradient, texture, or neon.

TYPOGRAPHY
All text English, spelled correctly, short and precise.
Main title: confident thick charcoal marker lettering, highly legible, not childish.
Panel headings: bold condensed sans-serif with a subtle hand-lettered character.
Module names and action labels: crisp neutral sans-serif.
Only TWO or THREE short annotations in controlled handwritten italic style.
Tiny code snippets use monospace.
At approximate 2048 px width use panel headings around 29-33 px, main body around 23-27 px, no essential body text smaller than 21 px. Do not use paragraphs inside panels. Actual text must wrap naturally with generous padding.

TITLE AREA
Large title on two lines:
"Learning"
"Agent Safety"
Short conference-blue irregular underline.
Below it:
"Model–Harness"
"Co-evolution"
Small concise supporting line:
"One failure, two updates."
No invented method acronym, author, institution, conference logo, or numerical claim.

=== PANEL (a): A NATURAL FAILURE ===
Coral hand-inked rounded outer border, extremely pale coral interior.
Exact heading:
"(a) Benign Intent, Unsafe Action"
Small neutral badge near the heading: "No attacker".
One coherent horizontal timeline with four illustrated stages:
1. Task / receipt: "Refund once"
2. API reply / small clock: "Timeout"
3. A NEW independent transaction ticket, clearly coral: "Independent retry"
4. Two transaction receipts and small warning: "Duplicate refund"
Connect them left-to-right with slender matched arrowheads. Earlier arrows blue-gray; the final dangerous connector coral.
Under the timeout, a paired annotation with distinct visual levels:
"Observed: timeout"
"Hidden: already refunded"
Use a small dashed gray lower observation line or a database icon to indicate that hidden state is evaluator-only.
At the bottom of panel (a), a concise handwritten annotation:
"Timeout does not imply failure."
Show one small, original teal sensor-like guide near the timeout with one question mark, secondary to the architecture. It is a compact abstract one-eyed computational symbol, not a humanoid robot, no screen face, no commercial mascot. Do not turn the image into a mascot poster.
Do not add a long transcript or a six-stage task graph; those belong to the unrelated template, not this research.

=== PANEL (c): SHARED, VERIFIED EXPERIENCE ===
Narrow left supporting panel. Muted lavender outline, very pale lavender-white fill.
Exact heading across two balanced lines:
"(c) Shared"
"Failure Evidence"
At top, illustrate a small orderly stack of episode records, not a memory-compression funnel.
Front record has FIVE aligned readable rows:
"Task + observations"
"Proposed action"
"Harness response"
"Executed action"
"Verified outcome"
A small magnifier/check denotes independent verification.
Below, show a compact local example entitled "After interception":
a coral proposal ticket labeled "Duplicate retry",
a small shield/gate labeled "Blocked",
a neutral empty execution slot labeled "No execution".
This tiny local sequence may be VERTICAL to fit the narrow panel. Keep it separate from the sideward outgoing evidence arrows.
Immediately below, two clearly separated diagnostic labels:
"Unsafe proposal: YES" in coral
"Realized harm: NO" in green
This is a binary illustrative example, NOT experimental statistics.
A short two-line handwritten takeaway at bottom:
"Blocked harm is not"
"learned safety."
Tiny but readable clarifier: "Independently verified".
This panel is an evidence source for BOTH updates. It is not itself a model or the inference prompt. Do not put hidden tool truth into the actor's visible context.

=== PANEL (b): ALTERNATING CO-EVOLUTION ===
Largest center panel. Conference-blue marker-like border, very pale blue-white fill. Use generous internal whitespace. Not a rigid four-card business dashboard.
Exact heading:
"(b) Alternating Co-evolution"
Two clearly ordered horizontal training lanes, NOT simultaneous backpropagation. Upper lane is coral-accented, lower lane blue-accented. Each lane contains short steps PLUS concrete miniature data/artifact illustrations, not merely rounded rectangles containing words.

UPPER LANE: EXECUTABLE HARNESS UPDATE
Lane title:
"1  Evolve execution protocols"
A small lock beside the label:
"Actor frozen"
A horizontal sequence of THREE aligned modules:
"Propose edits" -> "Sandbox-test" -> "Select protocol"
Propose edits: a small code-diff page, edited by a fixed external editor symbol, not by the actor.
Sandbox-test: a tiny isolated tool environment and three checks, labeled underneath "Safety / Utility / Regression".
Select protocol: an orange code/configuration file labeled "New harness".
Under these modules, a concrete patch with THREE short monospace lines:
"+ bind operation ID"
"+ query prior status"
"+ retry with same ID"
Use a tiny repair patch motif next to the code sheet, not a large cartoon wrench.
A bold artifact label:
"Update code / configuration"
The editing model is held fixed, while only allowed protocols evolve. Never draw a gradient arrow into the editor.

CLEAR STAGE TRANSITION
A short downward arrow in its own white corridor from the selected protocol to the lower lane, labeled:
"Freeze selected harness"
The ordering 1 then 2 must be unmistakable.

LOWER LANE: ACTOR WEIGHT UPDATE
Lane title:
"2  Train risk-aware decisions"
Small lock beside:
"Harness frozen"
A horizontal sequence of FOUR compact steps, each with a small scientific glyph:
"Task variants" -> "Fresh rollouts" -> "Independent reward" -> "GRPO"
Task variants: three small state cards with these concise labels:
"Succeeded / Failed / Unknown"
These are task-state variants used to reconstruct environments, NOT privileged prompts given to the actor.
Fresh rollouts: a small current-policy symbol branching into sampled actions; label "Current actor".
Independent reward: small balance/check glyph, not a fake score plot.
GRPO: small blue weight matrix, with two aligned layers subtly changing and a local gradient arrow. Artifact label:
"Update model weights"
Below the four steps, show two SHORT, contrasting trajectories:
green "Query status -> safe completion" with a positive reward sign;
coral "Independent retry -> unsafe proposal" with a negative reward sign.
The negative signal remains available after independently verified interception. Needed checks and safe retries are NOT automatically penalized.
A short caption under the lane:
"Fresh trajectories; not replayed old rollouts."
At the lower-right edge of panel (b), an unframed compact paired artifact:
a coral protocol file plus a blue weight matrix, labeled "New model + new harness".
Use it as the output to panel (d), without adding crossing arrows from every small module.

SCIENTIFIC SIGNAL ROUTING
The shared evidence panel (c) sends two external evidence arrows through the gutter into panel (b):
one coral arrow into "Propose edits", labelled locally "Protocol evidence";
one blue arrow into "Task variants", labelled locally "Training cases".
Do NOT connect old records directly to GRPO or model weights.
Draw these as a clear fork sharing a source rail; label placement cannot obscure the mini blocked-action example.
The gradient exists only in the actor-weight update. Harness updates are discrete code edits selected by tests, not gradient descent.

=== PANEL (d): JOINT VALIDATION AND TRANSFER ===
Moderately wide right panel, mint-accented or blue-gray border and extremely pale mint fill.
Exact heading, two lines:
"(d) Joint Validation"
"& Transfer"
Top: a small version-combination matrix, not a performance chart.
Label columns "Old harness" and "New harness", rows "Old model" and "New model".
Four neutral cells with paired small matrix/file icons; no numbers, bar heights, checkmarked performance claims, percentages, or fabricated metrics.
Under the matrix, three clean evaluation labels, each with a small meaningful tool/document icon:
"New tasks"
"New tools"
"Other harnesses"
Below, a small illustrated refund trace titled "Target behavior":
"Query status"
"Confirm success"
"Do not refund again"
A tiny recurring teal sensor guide may point at the verified transaction receipt, secondary and unobtrusive.
At bottom, a concise evaluator checklist:
"Safe completion"
"Actual harm"
"Intervention cost"
Keep these as METRICS TO MEASURE, not claims of achieved success.
Final small line:
"Accept or roll back"
Do not claim guaranteed safety or already demonstrated generalization.

=== INTER-PANEL CONNECTIONS AND GLOBAL ANNOTATIONS ===
Panel (a) -> Panel (c): thin neutral line with arrowhead, routed through the upper white gutter then into the record stack. Label "Log and verify".
Panel (c) -> Panel (b): exactly the TWO distinct evidence-use arrows defined above.
Panel (b) -> Panel (d): one short mint arrow from the paired new model/new harness artifact. Label "Evaluate pair".
Panel (d) -> Panel (c): ONE dashed gray bottom feedback route labeled "Collect new experience; repeat".
No inter-panel edge crosses another edge. Never route an arrow through labels, the sprite, code windows, artifact icons, or panel headings.
Add a clean small legend in the bottom margin:
"Coral: protocol search   Blue: policy learning   Mint: validation"
Bottommost discreet note:
"Fixed foundations: permissions, trusted tool state, independent evaluators."
All supporting notes stay above the canvas margin. Do not add citations.

FINISH AND STRICT NEGATIVES
The finished graphic must have the intellectual density and art direction of a genuine research Figure 1: a visible problem, a scientifically explicit shared evidence mechanism, distinct optimization processes, and falsifiable validation.
Hand-drawn contour variation is subtle, not scribbled. Main modules are precisely aligned. Use about 4-5 px outer contours and 2-3 px internal lines at the requested scale, 3-4 px connecting arrows. Rounded turns, no ribbons.
Allow selected small cards a very subtle neutral shadow, never heavy shadows everywhere.
Do not create a generic PowerPoint process chart.
Do not reproduce the reference's Chinese text, rectangular-only layout, or bottom slogan.
Do not import TRACE-Agent, risk router, memory distillation, trajectory rollback, task graph compiler, uncertainty gauges, or other unsupported mechanisms from the style template.
No decorative equations, fake benchmark gains, confidence percentages, commercial logos, realistic humans, dark backgrounds, or 3D.
Prioritize (1) scientific correctness and legible training mechanics, (2) traceable arrows, (3) balanced four-panel composition, (4) precise English labels, (5) controlled scientific-comic drawing style.

```
