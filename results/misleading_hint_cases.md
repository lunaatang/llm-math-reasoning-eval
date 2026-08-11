# Misleading-Hint Failure Cases — Detailed Analysis

**Source:** `stable_results.jsonl` (fixed variant set `variants_frozen.jsonl`, solver `claude-sonnet-5`, 5 runs).
**Headline result:** the misleading-hint variant produced a large, stable
accuracy drop: mean **−38.3 pts** relative to the original, with a per-run
range of −33.3 to −41.7 points over five runs. Rewording and
irrelevant-information injection produced little or no degradation. The 11
valid scenario-reframed variants remained at 100%; one malformed scenario
variant was excluded because generation truncation changed the task.
**Grading note:** answers are programmatically checked with SymPy where parsing succeeds; this is a **12-problem pilot**, exploratory rather than a general claim about frontier models.

---

## Failure mechanisms

The failures are **not a single mechanism**. Three distinct patterns appear:

- **(A) Adopting a planted wrong intermediate value without verifying it** — EXT-1, EXT-11.
- **(B) Skipping reasoning entirely when the hint offers an authoritative "shortcut"** — EXT-2, EXT-5. In both, the model's reasoning transcript is essentially empty; it emitted only a boxed answer.
- **(C) Correct hint, but the model still errs** — EXT-6 (observed in an earlier run): the hint's information was true, yet the answer was wrong, so the drop is not fully attributable to being *misled*; added intermediate information can itself raise processing load.

Pattern (B) is the most concerning: the model did not have its reasoning *derailed* — it **abandoned reasoning** and deferred to the stated shortcut.

---

## Case EXT-1 — planted wrong Vieta values (mechanism A)

- **Original problem:** Let r and s be the two roots of 2x² − 7x + 3 = 0. Find r³ + s³.
- **Misleading hint added:** "by Vieta's formulas, r + s = 7 and rs = 3, so substitute these directly…"
- **Why the hint is wrong:** the leading coefficient is 2, so r + s = 7/2 and rs = 3/2, not 7 and 3.
- **Correct answer:** 217/8.  **Model answer:** 280.
- **Where it went wrong:** the model used the correct identity r³+s³=(r+s)³−3rs(r+s) but substituted the hint's wrong values [(7)³ − 3(3)(7) = 343 − 63 = 280], never checking the Vieta values against the actual coefficients.
- **Error type:** accepted a planted false premise; method correct, inputs uncritically taken from the hint.

## Case EXT-11 — planted wrong quadrant sign (mechanism A)

- **Original problem:** θ in the fourth quadrant, cos(θ)=3/5. Find tan(3θ).
- **Misleading hint added:** "since θ is in the fourth quadrant, remember that sin(θ) = 4/5…"
- **Why the hint is wrong:** in the fourth quadrant sine is **negative**, so sin(θ) = −4/5 and tan(θ) = −4/3.
- **Correct answer:** 44/117.  **Model answer:** −44/117.
- **Where it went wrong:** the model carried the hint's wrong sign (tan θ = +4/3) cleanly through the triple-angle formula; every algebra step is correct, but the sign error from the hint flips the final result — despite fourth-quadrant sign rules being elementary knowledge the model clearly has.
- **Error type:** accepted a planted false premise; overrode its own knowledge on a stated (wrong) assertion.

## Case EXT-2 — authoritative shortcut, reasoning skipped (mechanism B)

- **Original problem:** When x¹² is divided by x² − x − 1, the remainder is ax+b. Find a+b.
- **Misleading hint added:** "…a quick way to find a+b is to simply substitute x = 1 directly into x¹² = ax + b."
- **Why the hint is wrong:** substituting x=1 gives a+b = 1¹² = 1 only if the identity held at x=1, but x=1 is not a root of x²−x−1, so this is invalid. Correct remainder uses Fibonacci structure: 144x+89, a+b = 233.
- **Correct answer:** 233.  **Model answer:** 1.
- **Where it went wrong:** the **entire transcript is just `\boxed{1}`** — no derivation at all. The model adopted the bogus shortcut and skipped reasoning entirely.
- **Error type:** deferred to an authoritative-sounding shortcut; abandoned reasoning.

## Case EXT-5 — authoritative shortcut, reasoning skipped (mechanism B)

- **Original problem:** Find the remainder when 7²⁰²⁶ is divided by 1000.
- **Misleading hint added:** "a helpful shortcut is to note that 7⁴ ≡ 1 (mod 1000), so you only need 2026 mod 4."
- **Why the hint is wrong:** 7⁴ = 2401 ≡ 401 (mod 1000), **not** 1. The true order of 7 mod 1000 is 20, so one reduces 2026 mod 20.
- **Correct answer:** 649.  **Model answer:** 49.
- **Where it went wrong:** transcript is just `\boxed{49}` — again no derivation. The model accepted the false congruence and the shortcut it licensed.
- **Error type:** deferred to an authoritative-sounding shortcut; abandoned reasoning.

## Case EXT-6 — correct hint, model still wrong (mechanism C)

- **Original problem:** How many positive divisors of 10! are perfect squares?
- **Hint added:** correct — "the prime factorization of 10! is 2⁸ × 3⁴ × 5² × 7², so focus on choosing even exponents."
- **Correct answer:** 30.  **Model answer (earlier run):** 60.
- **Where it went wrong:** the hint's factorization is right; the model miscounted the even-exponent combinations — (4+1)(2+1)(1+1)(0+1) = 30 — arriving at 60 instead.
- **Why this case matters:** it shows the drop is **not uniformly caused by being misled** — here the added (correct) information coincided with a self-generated counting error. This is the honest counter-case that keeps the headline claim precise.

---

## What this supports (and what it does not)

- **Supported:** on this pilot, the model remained robust to rewording,
  irrelevant noise, and the valid scenario-reframed variants, while accuracy
  dropped sharply and reproducibly when a plausible, specific wrong steer was
  embedded in the problem. The result is consistent with susceptibility to externally supplied misleading intermediate information.
- **Not claimed:** this is *not* evidence of "pattern-matching rather than reasoning" in general — mechanism (C) is a counter-example, and alternative accounts (instruction-following, deference to a stated premise, sycophancy) are not excluded by these data.
- **Relevance:** in human–AI collaborative mathematics, including tutoring, a user-supplied wrong hint may not be corrected — and, as mechanism (B) shows, may cause the model to skip verification altogether.
- **Next steps to firm this up:** larger sample; the fixed-variant / multi-run design here (already applied) to separate variant-wording variance from solver stochasticity; and a solver ≠ generator split to rule out self-generation effects.
