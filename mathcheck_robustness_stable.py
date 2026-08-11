"""
mathcheck_robustness_stable.py
------------------------------
A more rigorous version of mathcheck_robustness.py, built to address a real
methodological problem found during piloting: when variants are regenerated on
every run, the misleading-hint accuracy drop swings widely between runs (8-25
points across three pilot runs). That variance comes from two sources at once
-- (a) the variant text itself changes each run, and (b) the solver is
stochastic. Conflating them makes the headline number unreproducible.

This script separates the two phases so the result is stable and auditable:

  PHASE 1 (generate once):  build a FIXED variant set and freeze it to disk.
                            Run this a single time; the exact problems every
                            later run sees are then fixed and inspectable.

  PHASE 2 (evaluate N times): solve the frozen variant set R times and report
                            mean accuracy per variant, the standard deviation,
                            and the mean robustness drop with its spread.

It also separates the three model roles the review flagged:
  --generator-model : writes the variants (Phase 1)
  --solver-model    : answers them (Phase 2)
  --judge           : not used here (grading is SymPy-symbolic), but kept as a
                      documented seam for a future LLM-judge cross-check.

Grading reuses eval_pipeline.py. Answers are programmatically checked with
SymPy where parsing succeeds -- this is NOT a formally verified benchmark.
All results are a small pilot (default 12 problems); treat findings as
exploratory signals, not general claims about frontier models.

Usage:
  # Phase 1 -- freeze the variant set once (uses the generator model)
  python3 mathcheck_robustness_stable.py generate \
      --problems problems_external.json --n 12 \
      --generator-model claude-sonnet-5 --variants-out variants_frozen.jsonl

  # Phase 2 -- solve the frozen set 5 times with the solver model
  python3 mathcheck_robustness_stable.py evaluate \
      --variants-in variants_frozen.jsonl \
      --solver-model claude-sonnet-5 --runs 5
"""
import json, os, argparse, datetime
import pandas as pd
import eval_pipeline as ep
import mathcheck_robustness as mc  # reuse VARIANT_TYPES and the variant prompts


# ---------------------------------------------------------------------------
# PHASE 1: generate and freeze the variant set
# ---------------------------------------------------------------------------
def phase_generate(args):
    no_key = "ANTHROPIC_API_KEY" not in os.environ
    gen_fn = mc.gen_variant_mock if (args.gen == "mock" or no_key) else mc.gen_variant_llm
    if gen_fn is mc.gen_variant_mock:
        print(">>> Generating variants with the MOCK generator (no key or --gen mock).")

    problems = json.load(open(args.problems))[:args.n]
    frozen = []
    for p in problems:
        for vt in mc.VARIANT_TYPES:
            text = gen_fn(p["problem"], vt, args.generator_model)
            frozen.append({
                "id": p["id"], "category": p["category"], "difficulty": p.get("difficulty"),
                "variant": vt, "variant_problem": text,
                "gold": p["answer"],
            })
    with open(args.variants_out, "w") as f:
        for row in frozen:
            f.write(json.dumps(row) + "\n")

    cfg = {
        "phase": "generate",
        "generator_model": (args.generator_model if gen_fn is mc.gen_variant_llm else "mock"),
        "problems_file": args.problems,
        "n_problems": len(problems),
        "variant_types": mc.VARIANT_TYPES,
        "n_frozen_variants": len(frozen),
        "run_date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "note": "Frozen variant set. Every Phase-2 run solves exactly these texts, "
                "so run-to-run variance reflects only solver stochasticity, not "
                "changing variant wording.",
    }
    with open(args.variants_out.replace(".jsonl", "_genconfig.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"Froze {len(frozen)} variants ({len(problems)} problems x {len(mc.VARIANT_TYPES)} types) "
          f"-> {args.variants_out}")


# ---------------------------------------------------------------------------
# PHASE 2: solve the frozen set R times, aggregate with mean +/- std
# ---------------------------------------------------------------------------
def phase_evaluate(args):
    no_key = "ANTHROPIC_API_KEY" not in os.environ
    use_mock_model = args.mock_model or no_key
    if use_mock_model:
        print(">>> Solving with the MOCK solver (no key or --mock-model). Numbers NOT real.\n")

    frozen = [json.loads(l) for l in open(args.variants_in)]
    per_run_acc = []      # list of {variant: accuracy} dicts, one per run
    all_rows = []
    for run_idx in range(args.runs):
        run_correct = {vt: [] for vt in mc.VARIANT_TYPES}
        for row in frozen:
            prompt = ep.PROMPT_TEMPLATE.format(problem=row["variant_problem"])
            if use_mock_model:
                raw = ep.call_mock_model(prompt, {**row, "answer": row["gold"],
                                                  "difficulty": row.get("difficulty", 3)})
            else:
                raw = ep.call_anthropic_model(prompt, row, model=args.solver_model)
            pred = ep.extract_boxed_answer(raw)
            correct = ep.grade(pred, row["gold"])
            run_correct[row["variant"]].append(correct)
            all_rows.append({**{k: row[k] for k in ("id", "category", "variant", "variant_problem", "gold")},
                             "run": run_idx, "predicted": pred, "correct": correct,
                             "raw_response": raw})
        per_run_acc.append({vt: (sum(v) / len(v) if v else float("nan"))
                            for vt, v in run_correct.items()})
        print(f"  run {run_idx+1}/{args.runs} done")

    acc_df = pd.DataFrame(per_run_acc)[mc.VARIANT_TYPES]

    # save full transcripts and per-run results
    with open(args.out, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")

    # aggregate
    print("\nAccuracy per variant  (mean +/- std over", args.runs, "runs):")
    for vt in mc.VARIANT_TYPES:
        print(f"  {vt:24s} {acc_df[vt].mean()*100:5.1f}%  +/- {acc_df[vt].std(ddof=0)*100:4.1f}")
    base = acc_df["original"].mean()
    print("\nMean robustness drop vs. original (positive = worse under variation):")
    for vt in mc.VARIANT_TYPES:
        if vt == "original":
            continue
        drops = (acc_df["original"] - acc_df[vt]) * 100
        print(f"  {vt:24s} {drops.mean():+5.1f} pts  (per-run range {drops.min():+.1f} to {drops.max():+.1f})")

    print("\nRead this as a pilot signal, not a fixed effect: report the mean and")
    print("spread, and note that a drop consistent across runs is more credible")
    print("than any single run's number.")

    cfg = {
        "phase": "evaluate",
        "variants_in": args.variants_in,
        "solver_model": (args.solver_model if not use_mock_model else "mock"),
        "runs": args.runs,
        "max_tokens_solver": 4096,
        "run_date_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "per_run_accuracy": [{k: float(v) for k, v in d.items()} for d in per_run_acc],
        "note": "Frozen-variant multi-run pilot. SymPy-checked answers where parsing "
                "succeeds; not formally verified. Exploratory, not a general claim.",
    }
    with open(args.out.replace(".jsonl", "_run_config.json"), "w") as f:
        json.dump(cfg, f, indent=2)
    print(f"\nWrote per-run transcripts to {args.out} and config to "
          f"{args.out.replace('.jsonl', '_run_config.json')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Phase 1: freeze a variant set")
    g.add_argument("--problems", default="problems_external.json")
    g.add_argument("--n", type=int, default=12)
    g.add_argument("--generator-model", default="claude-sonnet-5")
    g.add_argument("--gen", choices=["llm", "mock"], default="llm")
    g.add_argument("--variants-out", default="variants_frozen.jsonl")
    g.set_defaults(func=phase_generate)

    e = sub.add_parser("evaluate", help="Phase 2: solve the frozen set R times")
    e.add_argument("--variants-in", default="variants_frozen.jsonl")
    e.add_argument("--solver-model", default="claude-sonnet-5")
    e.add_argument("--runs", type=int, default=5)
    e.add_argument("--mock-model", action="store_true")
    e.add_argument("--out", default="stable_results.jsonl")
    e.set_defaults(func=phase_evaluate)

    args = ap.parse_args()
    args.func(args)
