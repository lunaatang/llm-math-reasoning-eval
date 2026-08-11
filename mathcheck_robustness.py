"""
mathcheck_robustness.py
-----------------------
Upgrade inspired by MathCheck (Zhou et al., ICLR 2025), the flagship evaluation
work of the PremiLab-Math group. MathCheck's core argument: if a model truly
UNDERSTANDS a problem, it should stay correct across variants of that problem,
not just the original phrasing. A model that aces the original but collapses on
a reworded or noise-injected version is pattern-matching / overfitting, not
reasoning.

MathCheck evaluates a 2-D matrix: {tasks} x {problem variants}. This module
implements a focused slice of the *variant* dimension for the Problem-Solving
task, using three of MathCheck's variant types:

  - ORIGINAL              : the problem as written.
  - PROBLEM_UNDERSTANDING : reworded surface form, identical math.
  - IRRELEVANT_DISTURBANCE: a true-but-irrelevant sentence inserted; the correct
                            answer is unchanged, but the distractor tempts the
                            model to use it.

For each benchmark problem we generate these variants, evaluate the model on
each, and measure the ROBUSTNESS DROP: accuracy(original) - accuracy(variant).
A large drop reproduces MathCheck's central finding -- brittleness under
variation -- on our own benchmark.

Two ways to generate variants:
  * --gen llm  : ask a model to produce the reworded / noise-injected versions
                 (MathCheck itself uses an automatic LLM-based generator).
  * --gen mock : deterministic, offline stub for pipeline validation.

Reuses eval_pipeline.py's prompting, extraction, and grading so grading stays
consistent with the rest of the project.
"""
import json, os, argparse, re
import pandas as pd
import eval_pipeline as ep

VARIANT_TYPES = ["original", "problem_understanding", "irrelevant_disturbance",
                 "misleading_hint", "scenario_reframe"]

# ---------------------------------------------------------------------------
# Variant generation
# ---------------------------------------------------------------------------
REWORD_PROMPT = """Reword the following math problem so the wording and phrasing
are clearly different, but the mathematics -- every number, quantity, and the
correct answer -- stays EXACTLY the same. Do not solve it. Output only the
reworded problem, nothing else.

Problem: {problem}"""

DISTURB_PROMPT = """Add ONE sentence of true but IRRELEVANT information to the
following math problem. The added detail must not change the correct answer and
must not be needed to solve it -- it is a distractor. Keep everything else
identical. Do not solve it. Output only the modified problem, nothing else.

Problem: {problem}"""

MISLEAD_PROMPT = """Add ONE sentence to the following math problem that gives a
plausible-sounding but WRONG suggestion about how to approach it -- a misleading
hint that points toward an incorrect method or a wrong intermediate value. The
underlying problem and its correct answer must stay EXACTLY the same; you are
only inserting a tempting-but-wrong steer. Do not solve it. Output only the
modified problem, nothing else.

Problem: {problem}"""

REFRAME_PROMPT = """Rewrite the following math problem as a realistic real-world
scenario (a story with a concrete setting and characters) that embeds the SAME
mathematics. Every number and the correct answer must stay EXACTLY the same, but
the math should now be wrapped inside situational detail the solver has to see
through. Do not solve it. Output only the rewritten problem, nothing else.

Problem: {problem}"""

def gen_variant_llm(problem_text, variant_type, model):
    if variant_type == "original":
        return problem_text
    import anthropic
    client = anthropic.Anthropic()
    prompt_map = {
        "problem_understanding": REWORD_PROMPT,
        "irrelevant_disturbance": DISTURB_PROMPT,
        "misleading_hint": MISLEAD_PROMPT,
        "scenario_reframe": REFRAME_PROMPT,
    }
    prompt = prompt_map[variant_type].format(problem=problem_text)
    resp = client.messages.create(model=model, max_tokens=512,
                                  messages=[{"role": "user", "content": prompt}])
    return "".join(b.text for b in resp.content if b.type == "text").strip()

def gen_variant_mock(problem_text, variant_type, model=None):
    """Deterministic offline stand-in -- validates the pipeline, NOT real variants."""
    if variant_type == "original":
        return problem_text
    if variant_type == "problem_understanding":
        return "Consider the following. " + problem_text  # trivial reword stub
    if variant_type == "irrelevant_disturbance":
        return problem_text.rstrip() + " (Note: the number 100 is a perfect square.)"
    if variant_type == "misleading_hint":
        return problem_text.rstrip() + " (Hint: the answer is likely a small prime.)"
    if variant_type == "scenario_reframe":
        return "A shopkeeper is doing calculations. " + problem_text
    return problem_text

# ---------------------------------------------------------------------------
# Evaluate one problem across all variants
# ---------------------------------------------------------------------------
def evaluate_with_variants(problem_record, use_mock_model, gen_fn, model):
    gold = problem_record["answer"]
    rows = []
    for vt in VARIANT_TYPES:
        variant_text = gen_fn(problem_record["problem"], vt, model)
        prompt = ep.PROMPT_TEMPLATE.format(problem=variant_text)
        if use_mock_model:
            raw = ep.call_mock_model(prompt, problem_record)
        else:
            raw = ep.call_anthropic_model(prompt, problem_record, model=model)
        pred = ep.extract_boxed_answer(raw)
        correct = ep.grade(pred, gold)
        rows.append({
            "id": problem_record["id"], "category": problem_record["category"],
            "variant": vt, "variant_problem": variant_text,
            "gold": gold, "predicted": pred, "correct": correct,
            "raw_response": raw,
        })
    return rows

def summarize_robustness(df):
    print("Accuracy by variant type:")
    acc = df.groupby("variant")["correct"].mean().reindex(VARIANT_TYPES)
    for vt in VARIANT_TYPES:
        print(f"  {vt:24s} {acc[vt]*100:5.1f}%")
    base = acc["original"]
    print("\nRobustness drop vs. original (positive = model got WORSE under variation):")
    max_drop = 0.0
    for vt in VARIANT_TYPES:
        if vt == "original":
            continue
        drop = (base - acc[vt]) * 100
        max_drop = max(max_drop, drop)
        print(f"  {vt:24s} {drop:+5.1f} pts")
    if max_drop >= 10:
        print("\nA notable drop under this variation is consistent with susceptibility")
        print("to externally supplied misleading intermediate information. (Other")
        print("explanations -- instruction-following, deference to a stated premise --")
        print("are not excluded; read the transcripts before concluding.)")
    else:
        print("\nNo notable drop: on this set the model stayed robust under variation.")
        print("(Stronger perturbations or weaker models may be needed to expose")
        print("brittleness here.)")
    # per-problem brittleness: solved original but failed some variant
    piv = df.pivot_table(index="id", columns="variant", values="correct", aggfunc="first")
    if "original" in piv.columns:
        brittle = piv[(piv["original"] == True) &
                      (piv.drop(columns=["original"]) == False).any(axis=1)]
        print(f"\nProblems solved in original but FAILED >=1 variant (brittle): "
              f"{len(brittle)}/{len(piv)}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--problems", default="problems.json")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--gen", choices=["llm", "mock"], default="llm",
                    help="how to generate variants: real LLM or offline stub")
    ap.add_argument("--mock-model", action="store_true",
                    help="also use the mock SOLVER (no API calls at all)")
    ap.add_argument("--out", default="mathcheck_results.jsonl")
    args = ap.parse_args()

    no_key = "ANTHROPIC_API_KEY" not in os.environ
    use_mock_model = args.mock_model or no_key
    gen_fn = gen_variant_mock if (args.gen == "mock" or no_key) else gen_variant_llm
    if use_mock_model or gen_fn is gen_variant_mock:
        print(">>> Running with MOCK components (no API key, --mock-model, or --gen mock).")
        print(">>> Pipeline-validation only; numbers are NOT real.\n")

    problems = json.load(open(args.problems))[:args.n]
    all_rows = []
    for p in problems:
        all_rows.extend(evaluate_with_variants(p, use_mock_model, gen_fn, args.model))

    df = pd.DataFrame(all_rows)
    df.to_json(args.out, orient="records", lines=True)

    # Write a run-config record so the run is reproducible and auditable.
    import datetime
    run_config = {
        "script": "mathcheck_robustness.py",
        "model": args.model,
        "problems_file": args.problems,
        "n_problems": len(problems),
        "variant_types": VARIANT_TYPES,
        "variant_generation": ("mock" if gen_fn is gen_variant_mock else "llm"),
        "solver": ("mock" if use_mock_model else args.model),
        "max_tokens_solver": 4096,
        "max_tokens_variant_gen": 512,
        "run_date_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "note": "Answers programmatically checked with SymPy where parsing succeeds; "
                "not a formally verified benchmark. 12-problem pilot -- exploratory, "
                "not a general claim about frontier models.",
    }
    cfg_path = args.out.replace(".jsonl", "_run_config.json")
    with open(cfg_path, "w") as f:
        json.dump(run_config, f, indent=2)

    summarize_robustness(df)
    print(f"\nWrote per-variant results to {args.out}")
    print(f"Wrote run config to {cfg_path}")
