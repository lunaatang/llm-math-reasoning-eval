# Judge Validation — Does the LLM-as-Judge Agree with a Human?

The step-level reasoning analysis (`reasoning_analysis.py`) uses an LLM as a
verifier ("judge") to label each reasoning step. An LLM judging an LLM is only
meaningful if the judge itself is reliable. This is an inter-rater agreement
study between the judge and a human annotator.

## Method

- **Annotation set:** 75 steps (after excluding one truncated variant whose
  task was corrupted during generation). 45 are *natural* (real model steps
  from `stable_results.jsonl`); 30 are *synthetic* — hand-written, clearly
  labeled error steps added to balance the label distribution, since natural
  model output is overwhelmingly `valid` and a skewed set would let a trivial
  always-"valid" judge score ~96%. Synthetic rows are marked `source=synthetic`.
- **Fair comparison:** the judge receives the same accumulated prior steps of
  each chain that the human saw (grouped by problem+variant), so both judge the
  same information.
- **Rubric:** valid / computation_error / invalid_inference / unsupported_jump.

## Results

**Overall agreement: 63/75 = 84.0%.**
The set is error-enriched rather than naturally distributed: synthetic error
steps were added because natural model outputs were overwhelmingly labeled
`valid`. A trivial always-`valid` judge would score 43/75 ≈ 57% on this set.
The observed 84% raw agreement therefore provides evidence that the judge
distinguishes multiple categories, but it is not a definitive reliability
estimate.
| Human label | Judge agreement |
|---|---|
| valid | 40/43 = 93% |
| invalid_inference | 10/12 = 83% |
| computation_error | 7/10 = 70% |
| unsupported_jump | 6/10 = 60% |

Confusion matrix (rows = human, cols = judge):

|            | valid | comp_err | invalid | unsup_jump |
|------------|:-----:|:--------:|:-------:|:----------:|
| valid      |  40   |    0     |    0    |     3      |
| comp_err   |   0   |    7     |    3    |     0      |
| invalid    |   1   |    1     |   10    |     0      |
| unsup_jump |   4   |    0     |    0    |     6      |

**Most common disagreement:** human `unsupported_jump` → judge `valid` (4×).

## What this tells us

- The judge appears useful as a **pilot diagnostic**, achieving 84% raw
  agreement on this small mixed natural/synthetic set.
- `unsupported_jump` was the weakest category at 60%. The judge labeled four
  human-annotated unsupported jumps as valid, suggesting that it may sometimes
  be too permissive about omitted reasoning.
- The judge also incorrectly flagged three human-labeled valid steps as
  unsupported. Therefore, chain-validity estimates may be biased in either
  direction; the observed error pattern suggests possible upward bias, but the
  estimates should not be described as a strict upper bound.
- The boundaries between `computation_error` and `invalid_inference`, and
  between a concise valid step and an `unsupported_jump`, are partly
  judgment-dependent. Some disagreements may reflect rubric ambiguity rather
  than clear judge failures.
- Thirty of the 75 evaluated steps are synthetic. They are transparently
  identified in `annotation_sheet.csv` and should not be interpreted as
  naturally occurring error frequencies.

## Method limitations

This is a small pilot with a single human annotator. Thirty examples are
synthetic and intentionally cleaner than naturally occurring model errors.
Several category boundaries are inherently subjective, particularly
computation error versus invalid method and concise reasoning versus an
unsupported jump. A larger natural-error sample, per-row judge outputs, and a
second independent annotator would be needed for a stronger reliability claim.
