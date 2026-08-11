"""
judge_validation.py
-------------------
Second-priority rigor step: validate the LLM-as-judge used in
reasoning_analysis.py. An LLM verifier that grades reasoning steps is itself an
LLM, so its judgments can be wrong. Before trusting any "N% of chains are
valid" number, we must ask: how often does the judge agree with a human?

This script runs a small inter-rater-agreement study in three stages:

  STAGE 1 (prepare):  segment solutions into steps and write a blank
                      annotation sheet (annotation_sheet.csv) for a HUMAN to
                      fill in -- one label per step, chosen from a fixed rubric.

  STAGE 2 (human):    YOU fill in the `human_label` column by reading each step.
                      This is deliberately not automated -- the whole point is a
                      human reference to check the judge against.

  STAGE 3 (agreement): run the LLM judge on the same steps and compare to the
                      human labels: overall agreement, per-label agreement,
                      a confusion matrix, and the most common disagreement.

Label rubric (use these exact strings in the human_label column):
  valid                - step is mathematically correct and follows from context
  computation_error    - right method, arithmetic/algebra slip
  invalid_inference    - wrong method / unjustified logical step
  unsupported_jump     - conclusion asserted with no shown derivation

The judge's own {verdict, error_type} is mapped onto the same four labels so
the two are directly comparable.
"""
import json, os, argparse, csv
from collections import Counter, defaultdict

import reasoning_analysis as ra

RUBRIC = ["valid", "computation_error", "invalid_inference", "unsupported_jump"]

# Map the judge's (verdict, error_type) output onto the 4-label rubric.
def judge_to_label(verdict, error_type):
    if verdict == "valid":
        return "valid"
    if verdict == "unsupported":
        return "unsupported_jump"
    # verdict == "invalid"
    if error_type == "computation":
        return "computation_error"
    if error_type == "skipped_step":
        return "unsupported_jump"
    return "invalid_inference"  # "reasoning" or unspecified


# ---------------------------------------------------------------------------
# STAGE 1: prepare the annotation sheet
# ---------------------------------------------------------------------------
def stage_prepare(args):
    rows = [json.loads(l) for l in open(args.results)]

    # De-duplicate: the stable results file has R runs of each (id, variant).
    # Keep one transcript per (id, variant) so we don't label the same chain
    # multiple times.
    seen_pairs = set()
    unique = []
    for r in rows:
        key = (r.get("id", ""), r.get("variant", ""))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        unique.append(r)

    def steps_of(r):
        prob = r.get("variant_problem") or r.get("problem", "")
        return [{"problem_id": r.get("id", ""), "variant": r.get("variant", ""),
                 "step_index": i,
                 "problem": prob.replace("\n", " "),
                 "step_text": s.replace("\n", " "),
                 "source": "natural",
                 "human_label": ""}
                for i, s in enumerate(ra.segment_steps(r.get("raw_response", "")))]

    # WHOLE-TRANSCRIPT sampling: include EVERY step of a selected transcript,
    # so each chain the annotator sees has its full before/after context and
    # 'unsupported_jump' can be judged reliably. Failing transcripts are
    # selected first (they carry the invalid_inference / unsupported_jump
    # labels that make the judge check meaningful), then correct ones, until we
    # reach roughly --max-steps steps -- we finish the current transcript
    # rather than cutting it mid-chain.
    incorrect = [r for r in unique if not r.get("correct", True)]
    correct = [r for r in unique if r.get("correct", True)]
    ordered = incorrect + correct

    out = []
    used = 0
    for r in ordered:
        chain = steps_of(r)
        if not chain:
            continue  # e.g. a transcript that skipped reasoning (just a boxed answer)
        out.extend(chain)
        used += 1
        if len(out) >= args.max_steps:
            break

    with open(args.sheet, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["problem_id", "variant", "step_index",
                                          "problem", "step_text", "source", "human_label"])
        w.writeheader()
        w.writerows(out)
    n_probs = len({(r["problem_id"], r["variant"]) for r in out})
    print(f"Wrote {len(out)} steps to {args.sheet}, covering {n_probs} COMPLETE "
          f"(problem, variant) transcripts (full chains, no mid-chain cuts).")
    print("Now open it and fill the human_label column using the rubric:")
    print("  ", ", ".join(RUBRIC))
    print("Save, then run:  python3 judge_validation.py agreement --sheet",
          args.sheet)


# ---------------------------------------------------------------------------
# STAGE 3: run the judge and compute agreement with the human labels
# ---------------------------------------------------------------------------
def stage_agreement(args):
    rows = list(csv.DictReader(open(args.sheet)))
    # Drop rows explicitly marked for exclusion (e.g. a truncated variant whose
    # task was corrupted during generation -- not a fair test of the judge).
    rows = [r for r in rows if not r.get("human_label", "").strip().lower().startswith("exclude")]
    labeled = [r for r in rows if r["human_label"].strip()]
    if not labeled:
        print("No usable human labels found in", args.sheet, "-- fill the human_label column first.")
        return
    bad = [r["human_label"] for r in labeled if r["human_label"].strip() not in RUBRIC]
    if bad:
        print("These human_label values are not in the rubric:", set(bad))
        print("Allowed:", RUBRIC, "(or 'exclude: <reason>' to drop a row)"); return

    use_mock = args.mock or ("ANTHROPIC_API_KEY" not in os.environ)
    if use_mock:
        print(">>> Judge running in MOCK mode -- agreement numbers are NOT real.\n")

    # Build prior-context per chain: the judge must see the SAME preceding steps
    # the human saw, or the two aren't judging the same information. Group by
    # (problem_id, variant), order by step_index, and accumulate prior steps.
    from collections import defaultdict as _dd
    chains = _dd(list)
    for r in labeled:
        chains[(r["problem_id"], r["variant"])].append(r)
    for key in chains:
        chains[key].sort(key=lambda r: int(r["step_index"]))

    pairs = []  # (human, judge)
    for key, chain in chains.items():
        prior_steps = []
        for r in chain:
            prior = "\n".join(prior_steps)
            step = r["step_text"]; prob = r["problem"]
            if use_mock:
                j = ra.verify_step_mock(prob, prior, step, int(r["step_index"]))
            else:
                j = ra.verify_step_llm(prob, prior, step, int(r["step_index"]),
                                       model=args.model)
            judge_label = judge_to_label(j.verdict, j.error_type)
            pairs.append((r["human_label"].strip(), judge_label))
            prior_steps.append(step)   # accumulate for the next step in this chain

    n = len(pairs)
    agree = sum(1 for h, jl in pairs if h == jl)
    print(f"Steps compared: {n}")
    print(f"Overall agreement: {agree}/{n} = {agree/n:.1%}\n")

    # per-label agreement (of the steps the human gave label L, how many did the judge match)
    print("Per-human-label agreement:")
    by_h = defaultdict(list)
    for h, jl in pairs:
        by_h[h].append(jl)
    for lab in RUBRIC:
        if by_h[lab]:
            m = sum(1 for jl in by_h[lab] if jl == lab)
            print(f"  {lab:20s} {m}/{len(by_h[lab])} = {m/len(by_h[lab]):.0%}")
    # warn if label distribution is too skewed to be informative
    if by_h["valid"] and len(by_h["valid"]) / n > 0.75:
        print("\n[!] Warning: 'valid' is >75% of the set. A trivial always-'valid'")
        print("    judge would score high here; agreement is not yet informative")
        print("    about error detection. Add more invalid / computation_error /")
        print("    unsupported_jump examples for a balanced check.")

    # confusion matrix
    print("\nConfusion matrix (rows = human, cols = judge):")
    hdr = "               " + " ".join(f"{l[:8]:>9s}" for l in RUBRIC)
    print(hdr)
    cm = defaultdict(lambda: Counter())
    for h, jl in pairs:
        cm[h][jl] += 1
    for h in RUBRIC:
        row = " ".join(f"{cm[h][jl]:>9d}" for jl in RUBRIC)
        print(f"  {h[:13]:13s} {row}")

    # most common disagreement
    dis = Counter((h, jl) for h, jl in pairs if h != jl)
    if dis:
        (h, jl), c = dis.most_common(1)[0]
        print(f"\nMost common disagreement: human '{h}' -> judge '{jl}' ({c}x)")
    else:
        print("\nNo disagreements.")

    # write a short report
    with open(args.out, "w") as f:
        f.write(f"Judge-validation agreement report\n")
        f.write(f"Steps compared: {n}\n")
        f.write(f"Overall agreement: {agree}/{n} = {agree/n:.1%}\n\n")
        f.write("Confusion matrix (rows=human, cols=judge): "
                + json.dumps({h: dict(cm[h]) for h in RUBRIC}) + "\n")
    print(f"\nWrote {args.out}")


def stage_template(args):
    """Append blank SYNTHETIC rows to the sheet so the annotator can hand-write
    a few clear, controlled error steps and reach a balanced label distribution.
    The natural (real model) rows stay; these synthetic rows are transparently
    marked source=synthetic. You write the step_text yourself -- the target
    label is pre-filled so you know what kind of error to construct."""
    import csv as _csv
    existing = list(_csv.DictReader(open(args.sheet)))
    fieldnames = ["problem_id", "variant", "step_index", "problem",
                  "step_text", "source", "human_label"]
    # how many of each label to add
    targets = {"computation_error": args.computation,
               "invalid_inference": args.invalid,
               "unsupported_jump": args.unsupported}
    new_rows = []
    k = 0
    for label, count in targets.items():
        for i in range(count):
            new_rows.append({"problem_id": f"SYNTH-{k}", "variant": "synthetic",
                             "step_index": 0,
                             "problem": "(write the problem context this step belongs to)",
                             "step_text": "(write a step that is a clear "
                                          f"{label} -- e.g. a wrong arithmetic result, "
                                          "an invalid inference, or a bare unjustified jump)",
                             "source": "synthetic", "human_label": label})
            k += 1
    with open(args.sheet, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(existing + new_rows)
    print(f"Appended {len(new_rows)} blank synthetic rows "
          f"({targets}) to {args.sheet}.")
    print("Open the sheet and replace each synthetic row's `problem` and "
          "`step_text` with a real, hand-written example of that error type.")
    print("Keep the pre-filled human_label. Then run: agreement.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare", help="Stage 1: write a blank annotation sheet")
    p.add_argument("--results", default="stable_results.jsonl",
                   help="jsonl with raw_response transcripts")
    p.add_argument("--sheet", default="annotation_sheet.csv")
    p.add_argument("--max-steps", type=int, default=30)
    p.set_defaults(func=stage_prepare)

    t = sub.add_parser("template", help="Stage 2b: append blank synthetic rows to balance labels")
    t.add_argument("--sheet", default="annotation_sheet.csv")
    t.add_argument("--computation", type=int, default=10)
    t.add_argument("--invalid", type=int, default=10)
    t.add_argument("--unsupported", type=int, default=10)
    t.set_defaults(func=stage_template)

    a = sub.add_parser("agreement", help="Stage 3: judge vs. human agreement")
    a.add_argument("--sheet", default="annotation_sheet.csv")
    a.add_argument("--model", default="claude-sonnet-5")
    a.add_argument("--mock", action="store_true")
    a.add_argument("--out", default="results/judge_validation_report.txt")
    a.set_defaults(func=stage_agreement)

    args = ap.parse_args()
    args.func(args)
