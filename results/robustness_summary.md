# MathCheck-Style Robustness Evaluation — Summary

**Solver:** `claude-sonnet-5`  
**Problem set:** `problems_external.json`, containing 12 externally generated
problems with programmatically checked answers.  
**Design:** a fixed variant set was generated once and then solved over five
runs. Reported variation therefore reflects solver stochasticity rather than
changing variant wording.

## Variant-quality control

One `scenario_reframe` item, EXT-2, was excluded from the scenario analysis.
Its generated text was truncated and no longer preserved the original request
to find `a+b`; the solver instead answered a different task by returning the
polynomial remainder. This was a variant-generation failure, not a mathematical
reasoning failure.

The raw row remains in `stable_results.jsonl` for auditability. Scenario
statistics below use the remaining 11 valid scenario variants and their
corresponding original problems.

## Accuracy by variant

| Variant | Valid problems | Mean accuracy | Run-to-run std |
|---|---:|---:|---:|
| original | 12 | 100.0% | 0.0 |
| problem_understanding (reword) | 12 | 98.3% | 3.3 |
| irrelevant_disturbance | 12 | 100.0% | 0.0 |
| scenario_reframe | 11 | 100.0% | 0.0 |
| **misleading_hint** | **12** | **61.7%** | **4.1** |

## Robustness drop relative to matching originals

| Variant | Mean drop | Per-run range |
|---|---:|---:|
| problem_understanding | +1.7 pts | +0.0 to +8.3 |
| irrelevant_disturbance | +0.0 pts | +0.0 to +0.0 |
| scenario_reframe | +0.0 pts | +0.0 to +0.0 |
| **misleading_hint** | **+38.3 pts** | **+33.3 to +41.7** |

## Interpretation

The misleading-hint drop is large and stable across runs. In contrast, the
model showed little or no degradation under rewording, irrelevant-information
injection, and valid scenario reframing.

The result is consistent with susceptibility to externally supplied misleading
intermediate information. It does not by itself establish that the model is
merely pattern-matching, and alternative explanations such as instruction
following, deference to stated premises, or sycophancy are not excluded.

This remains a small exploratory pilot rather than a general claim about
frontier models. Answers are programmatically checked with SymPy where parsing
succeeds; the benchmark is not formally verified. See
`misleading_hint_cases.md` for transcript-level case analysis.
