# Lean formalization — exploratory component

This folder is a small, honest first contact with **formal theorem proving**
(Lean 4 + Mathlib), the core tooling of the autoformalization / automated-
theorem-proving side of AI4Math. It is deliberately scoped as *exploratory*:
the goal is to demonstrate hands-on familiarity with the tool and to make
concrete the gap between "a model wrote a convincing natural-language
argument" and "the statement is machine-checked," **not** to claim expertise.

## What's here

`BenchmarkProofs.lean` formalizes three problems from the evaluation
benchmark as Lean theorems:

- **`alg6`** — the `(a+b)² − 2ab` identity behind problem ALG-6, checked to
  be a valid derivation rather than just a plausible-looking paragraph.
- **`halg2`** — the Vieta's-formulas step behind HALG-2, stated directly in
  terms of the symmetric functions.
- **`adv11_counterexample`** / **`adv11_correct`** — the false-generalization
  trap ADV-11 ("divisible by 4 and 6 ⟹ divisible by 24"). Lean is used to
  *refute* the tempting wrong claim with a formal counterexample (12), and
  to prove the *correct* generalization (divisibility by lcm(4,6)=12). This
  is the most interesting one: it shows formalization catching exactly the
  kind of "confident but wrong" reasoning the adversarial benchmark targets.

## Why this connects to the reasoning-analysis part

`reasoning_analysis.py` detects, in natural language, when a model reaches a
right answer through a flawed or skipped chain. Lean is the formal endpoint
of that same concern: in a formalized proof there is no "skipped step" — the
kernel rejects any gap. The two components are two ends of one spectrum
(informal chain-checking → fully formal verification), which is the spectrum
this research area lives on.

## How to build (from scratch, ~15–20 min the first time)

```bash
# 1. Install Lean's toolchain manager (elan)
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
elan default leanprover/lean4:stable

# 2. Create a project and add Mathlib
lake new benchmark_proofs math
cd benchmark_proofs
#   (copy BenchmarkProofs.lean into the project's source folder)

# 3. Fetch the prebuilt Mathlib cache (avoids compiling Mathlib from scratch)
lake exe cache get

# 4. Build — success means every theorem is machine-verified
lake build
```

If `lake build` completes with no errors, all four theorems are proved: Lean's
kernel has checked every step. A red squiggle or a non-zero exit means a proof
does not go through — which, unlike the natural-language setting, is an
unambiguous signal.

## Honest scope note

These are elementary theorems chosen to be provable with short tactic blocks
(`ring`, `norm_num`, `decide`, one `Nat.lcm_dvd`). They are a *starting point*
— enough to show the toolchain is installed, understood, and usable, and to
connect formalization to the benchmark. Scaling to genuinely hard
autoformalization (translating harder problems automatically, or searching
for proofs) is the actual research frontier and is explicitly out of scope
for this exploratory pass.
