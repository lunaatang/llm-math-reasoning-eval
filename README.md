# LLM Mathematical Reasoning: Category-Level Failure Analysis

An AI4Math evaluation project: benchmark a language model's mathematical
reasoning across 3 escalating difficulty tiers (62 problems total: 30
standard, 20 AIME-adjacent, 12 adversarial "reasoning-trap" problems), grade
answers with symbolic equivalence (not string matching), and — the actual
point of the project — analyze *why* the model fails where it fails, not
just how often.

## Files

- `results/` — frozen evidence from the actual runs: `robustness_summary.md` (multi-run stable numbers), `misleading_hint_cases.md` (per-case failure analysis with transcripts), plus the raw `*.jsonl` and `*_run_config.json` from each run. All findings here are a **12-problem pilot** — exploratory, not general claims; answers are SymPy-checked where parsing succeeds, not formally verified.

- `problems.json` — Tier 1: 30 standard problems (difficulty 1-3), 5
  categories. Ground-truth answers computed with `sympy` in
  `build_problems.py`, not hand-checked.
- `problems_hard.json` — Tier 2: 20 AIME/olympiad-adjacent, multi-step
  problems (difficulty 4-5), built after Tier 1 came back 100% correct and
  gave nothing to analyze.
- `problems_adversarial.json` — Tier 3: 12 problems targeting known LLM
  failure *patterns* (overcounting, extraneous roots, false generalization,
  complementary-counting traps) rather than raw step-count, built after
  Tier 2 also came back 100%.
- `build_problems.py` — regenerates `problems.json` from scratch and verifies
  every answer is well-formed. (Tiers 2 and 3 were built directly as JSON
  with the same sympy-verification discipline; see the notebook for the
  verification code.)
- `eval_pipeline.py` — the evaluation harness: prompting, answer extraction
  (handles nested-brace LaTeX like `\boxed{\dfrac{7}{25}}`), symbolic
  grading, aggregation, plotting, and a failure-analysis worksheet
  generator. Accepts `--problems <file>` and `--out-prefix <prefix>` to run
  any tier without overwriting another tier's results. Includes a
  deterministic mock model so the pipeline can be validated without an API
  key.
- `judge_validation.py` — **validates the LLM-as-judge** used in
  reasoning_analysis: builds a human-annotated, label-balanced set (natural +
  transparently-marked synthetic error steps), gives the judge the same prior
  context the human saw, and reports agreement. Result: 84% agreement vs. a 57%
  majority-class baseline, weakest on unsupported_jump (judge too lenient about
  skipped reasoning). See `results/judge_validation_summary.md` and notebook
  Section 12.
- `reasoning_analysis.py` — **step-level reasoning analysis** (project
  extension): segments each model solution into steps and verifies each one,
  surfacing "right answer but flawed/skipped reasoning" cases that answer-only
  grading hides. Has a no-API-key mock. See notebook Section 7.
- `mathcheck_robustness.py` — **robustness-under-variation** module aligned
  with MathCheck (Zhou et al., ICLR 2025), the target lab's flagship work:
  generates reworded and noise-injected variants of each problem and measures
  the accuracy drop, testing whether the model reasons robustly or just
  relies on surface cues rather than robust reasoning. See notebook Section 10.
- `lean_exploration/` — **formal-verification exploration**: three benchmark
  problems formalized as Lean 4 theorems, including a formal refutation of the
  ADV-11 false-generalization trap. See notebook Section 8 and the folder's
  own README.
- `llm_math_eval.ipynb` — the write-up: motivation, methodology, pipeline
  validation, real results across all 3 tiers, and the failure-analysis
  section documenting the harness bugs found (not genuine reasoning
  errors), with math background and discussion of limitations.

## How to run it for real

```bash
pip install anthropic sympy pandas matplotlib
export ANTHROPIC_API_KEY=sk-...          # or set up a different provider
                                          # (edit call_anthropic_model in
                                          # eval_pipeline.py if using a
                                          # different SDK/model)

# Tier 1 -- standard problems
python3 eval_pipeline.py --model claude-sonnet-5 --n 30

# Tier 2 -- AIME-adjacent, harder; --out-prefix keeps results separate
python3 eval_pipeline.py --model claude-sonnet-5 --n 20 \
    --problems problems_hard.json --out-prefix hard_

# Tier 3 -- adversarial reasoning-trap problems
python3 eval_pipeline.py --model claude-sonnet-5 --n 12 \
    --problems problems_adversarial.json --out-prefix adv_
```

Each run writes its own `{prefix}eval_results.jsonl` (every problem + full
reasoning transcript), `{prefix}fig_accuracy.png`, and
`{prefix}failure_analysis.txt`. Open the failure-analysis worksheet and, for
every missed problem, actually read the model's reasoning transcript and
answer the three worksheet questions (reasoning vs. computation error;
pattern across skill tags) — **don't trust the accuracy number until you've
done this**. In this project's own run, every apparent failure across all
three tiers turned out to be a harness bug (LaTeX parsing, token-budget
truncation), not a real reasoning error — see Section 5 of the notebook.

The real results and failure-analysis write-up are already in
`llm_math_eval.ipynb` (Sections 4-5) from this project's own run. If you
re-run against a different model, update those sections with the new
findings.

## Extending it

- Swap in a different model/provider by editing `call_anthropic_model`.
- Try self-consistency (sample the same problem N times, take a majority
  vote) and compare accuracy to single-sample — this is a well-known lever
  in the literature and would make a natural second experiment.
- Compare against a formal-verification benchmark (miniF2F via Lean/LeanDojo)
  for a "informal chain-of-thought vs. formal proof search" contrast — a
  natural extension toward the autoformalization side of AI4Math.

## Resume / interview material

**One-liner (space-constrained resume bullet):**

> Built an end-to-end LLM mathematical reasoning evaluation pipeline (62
> problems, 3 difficulty tiers); diagnosed that all observed "failures"
> traced to evaluation-harness bugs (LaTeX parsing, token-budget
> truncation) rather than genuine model reasoning errors, informing more
> rigorous benchmark design practices.

**Detailed version (project section / personal site):**

> **LLM Mathematical Reasoning Evaluation** (independent project)
> - Designed and built a full evaluation pipeline for LLM mathematical
>   reasoning: chain-of-thought prompting, symbolic (not string-based)
>   answer grading via `sympy`, and category/difficulty-level failure
>   analysis, tested against a self-authored, 62-problem benchmark
>   spanning 5 branches of mathematics across 3 escalating difficulty
>   tiers (standard competition math, AIME-adjacent multi-step problems,
>   and adversarial "reasoning-trap" problems targeting known LLM failure
>   patterns)
> - Discovered and fixed two evaluation-harness bugs (nested-brace LaTeX
>   answer parsing, insufficient token budget causing response
>   truncation) that were producing false "failures" — demonstrating that
>   model reasoning was in fact correct in every case, a finding with
>   direct relevance to interpreting published LLM math-benchmark results
> - Concluded that claude-sonnet-5 achieves 100% accuracy across all three
>   tiers of the benchmark, and documented the debugging process as
>   evidence that harness-design artifacts, not just model capability,
>   are a significant and underexamined source of error in LLM evaluation
>   research

**Spoken version (interview "tell me about a project"):**

> I built a project evaluating LLM mathematical reasoning. I designed a
> 62-problem benchmark across three difficulty tiers, including a set of
> problems specifically designed to trigger known LLM reasoning traps.
> While running it, I found several apparent "failures" — but after
> reading the full reasoning transcripts, I discovered every one traced
> back to bugs in my own evaluation script, not the model: once a LaTeX
> parsing bug and a token-budget limit were fixed, the model actually got
> everything right. That taught me that a lot of published "model X only
> gets Y% on this benchmark" results may partly reflect evaluation-harness
> artifacts rather than real reasoning gaps — which was the most valuable
> takeaway from the whole project.
