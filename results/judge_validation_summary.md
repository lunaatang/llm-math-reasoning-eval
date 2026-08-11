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
Because the set is balanced, a trivial always-"valid" judge would score only
43/75 ≈ 57% (the majority-class baseline). The judge's 84% is well above that,
so the agreement reflects genuine discrimination, not label skew.

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

- The judge is **reliable overall** (84%, well above the 57% baseline), so
  conclusions drawn from the step-level analysis are broadly trustworthy.
- Its **weakest category is `unsupported_jump` (60%)**, and its dominant error
  is calling an unsupported jump `valid` — i.e. it is **too lenient about
  skipped reasoning**, sometimes treating an unjustified leap as if it followed.
- **Implication:** any "fraction of chains fully valid" figure from this judge
  should be read as an **upper bound** — the judge under-detects exactly the
  skipped-reasoning failures that matter most for evaluating genuine reasoning.
- **Honesty note:** 30/75 steps are synthetic. They were necessary to test the
  judge on error types that are rare in natural output; they are transparently
  marked and should not be read as natural error frequencies.

## Method limitations

Single annotator; small pilot set; synthetic errors are cleaner than
naturally-occurring ones, so real-world judge accuracy on messy errors may be
lower. A second independent annotator and a larger natural-error sample would
firm this up.
