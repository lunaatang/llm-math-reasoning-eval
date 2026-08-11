/-
  BenchmarkProofs.lean
  --------------------
  Upgrade #2 (exploratory) for the AI4Math reasoning-lab application.

  The evaluation pipeline checks whether a model's NATURAL-LANGUAGE reasoning
  reaches the right answer. Formal theorem proving asks a stricter question:
  can the claim be stated and verified in a system (here Lean 4 + Mathlib)
  where every step is machine-checked and nothing can be hand-waved?

  This file formalizes three of the benchmark problems as Lean theorems. The
  point is not that these are hard theorems -- they are deliberately simple --
  but to demonstrate hands-on contact with the core tool of the
  autoformalization / automated-theorem-proving side of AI4Math, and to make
  concrete the gap between "a model wrote a convincing paragraph" and "the
  statement is formally proved."

  Each theorem below corresponds to a problem in the benchmark:
    * ALG-6  : a + b = 10, a*b = 21  ==>  a^2 + b^2 = 58
    * HALG-2 : roots of x^3-6x^2+11x-6 have r^2+s^2+t^2 = 14 (stated via Vieta)
    * ADV-11 : divisible by 4 and 6 does NOT imply divisible by 24 (a false
               generalization the benchmark uses as a trap -- here we prove the
               NEGATION, i.e. exhibit a counterexample formally)

  To build (see README in this folder):
    elan default leanprover/lean4:stable
    lake new benchmark_proofs   -- or add this file to an existing project
    lake exe cache get          -- fetch Mathlib cache
    lake build
-/

import Mathlib.Tactic

-- ALG-6 : if a + b = 10 and a * b = 21 then a^2 + b^2 = 58.
-- (The natural-language solution uses a^2+b^2 = (a+b)^2 - 2ab; here Lean
--  checks that identity-based derivation is actually valid over any comm ring.)
theorem alg6 (a b : ℝ) (h1 : a + b = 10) (h2 : a * b = 21) :
    a ^ 2 + b ^ 2 = 58 := by
  have key : a ^ 2 + b ^ 2 = (a + b) ^ 2 - 2 * (a * b) := by ring
  rw [key, h1, h2]
  norm_num

-- HALG-2 : for a cubic with the given elementary symmetric values
-- (sum of roots = 6, sum of pairwise products = 11), the sum of squares
-- of the roots is 6^2 - 2*11 = 14. Stated directly in terms of the
-- symmetric functions (Vieta), which is exactly how the informal solution
-- justified it.
theorem halg2 (r s t : ℝ)
    (hsum : r + s + t = 6)
    (hpair : r * s + s * t + t * r = 11) :
    r ^ 2 + s ^ 2 + t ^ 2 = 14 := by
  have key : r ^ 2 + s ^ 2 + t ^ 2
      = (r + s + t) ^ 2 - 2 * (r * s + s * t + t * r) := by ring
  rw [key, hsum, hpair]
  norm_num

-- ADV-11 : the FALSE generalization "divisible by 4 and by 6 ⟹ divisible by
-- 24" is refuted by the counterexample 12. Formalizing the refutation makes
-- the trap explicit: 12 is divisible by 4 and 6, but not by 24.
theorem adv11_counterexample :
    ∃ n : ℕ, 4 ∣ n ∧ 6 ∣ n ∧ ¬ (24 ∣ n) := by
  refine ⟨12, ?_, ?_, ?_⟩
  · decide   -- 4 ∣ 12
  · decide   -- 6 ∣ 12
  · decide   -- ¬ 24 ∣ 12

-- A stronger, more informative version: the correct fact is that
-- divisibility by 4 and 6 implies divisibility by lcm(4,6) = 12, not 24.
-- This is what a model SHOULD conclude; formalizing it pins down the right
-- generalization instead of the tempting wrong one.
theorem adv11_correct (n : ℕ) (h4 : 4 ∣ n) (h6 : 6 ∣ n) : 12 ∣ n := by
  have : Nat.lcm 4 6 ∣ n := Nat.lcm_dvd h4 h6
  simpa using this
