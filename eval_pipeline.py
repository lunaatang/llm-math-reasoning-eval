"""
eval_pipeline.py
-----------------
Evaluate an LLM's mathematical reasoning ability on the curated problem bank
(problems.json), following the standard "MATH-style" evaluation protocol:
chain-of-thought prompting + final answer extraction via \\boxed{}.

Usage:
    export ANTHROPIC_API_KEY=sk-...
    python3 eval_pipeline.py --model claude-sonnet-5 --n 30

If no API key is set, the script falls back to a deterministic MOCK model
so the full pipeline (prompt -> call -> parse -> grade -> aggregate -> plot)
can be validated end-to-end without spending API credits. Swap in a real
model to get real results.
"""
import json, re, os, argparse, time
import pandas as pd
import matplotlib.pyplot as plt
import sympy as sp

PROMPT_TEMPLATE = """Solve the following math problem. Think step by step,
showing your reasoning, and end your response with the final numeric answer
on its own line in the exact form:

Final Answer: \\boxed{{ANSWER}}

Problem: {problem}
"""

def extract_boxed_answer(text: str):
    """Find the LAST \\boxed{...} in the text, correctly handling nested
    braces (e.g. \\boxed{\\dfrac{7}{25}} -- a naive non-nested regex fails
    on this and silently returns None, which looks like a model failure
    but is actually a parsing bug)."""
    marker = r"\boxed{"
    starts = [i for i in range(len(text)) if text.startswith(marker, i)]
    if not starts:
        return None
    start = starts[-1] + len(marker)
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    if depth != 0:
        return None  # unbalanced braces, malformed
    return text[start:i-1].strip()

def normalize_latex_answer(s: str) -> str:
    """Convert simple LaTeX fraction notation to a form sympy can parse,
    e.g. '\\dfrac{7}{25}' or '\\frac{7}{25}' -> '(7)/(25)'."""
    if s is None:
        return s
    s = re.sub(r"\\d?frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", s)
    s = s.replace("\\", "").replace("$", "").strip()
    return s

def grade(predicted: str, gold: str) -> bool:
    """Compare predicted vs gold answer, tolerant of equivalent numeric/rational
    forms AND of simple LaTeX fraction notation (\\frac, \\dfrac)."""
    if predicted is None:
        return False
    try:
        p = sp.nsimplify(sp.sympify(normalize_latex_answer(predicted)))
        g = sp.nsimplify(sp.sympify(normalize_latex_answer(gold)))
        return bool(sp.simplify(p - g) == 0)
    except Exception:
        return predicted.strip() == gold.strip()

# ---------------- Model backends ----------------
def call_mock_model(prompt, problem_record):
    """Deterministic stand-in used only to validate the pipeline runs end-to-end.
    Gets easy problems right, harder problems right ~50% of the time, to produce
    a non-trivial (but fake) difficulty gradient for testing plotting/aggregation code.
    NOT a real evaluation -- replace with call_anthropic_model for real results."""
    import hashlib
    seed = int(hashlib.md5(problem_record['id'].encode()).hexdigest(), 16)
    difficulty = problem_record['difficulty']
    correct_prob = {1: 0.95, 2: 0.65, 3: 0.35, 4: 0.5, 5: 0.25}.get(difficulty, 0.5)
    is_correct = (seed % 1000) / 1000 < correct_prob
    ans = problem_record['answer'] if is_correct else str(sp.nsimplify(problem_record['answer']) + 1)
    fake_reasoning = f"[MOCK MODEL -- not a real solution] ... Final Answer: \\boxed{{{ans}}}"
    return fake_reasoning

def call_anthropic_model(prompt, problem_record, model="claude-sonnet-5"):
    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    resp = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    if resp.stop_reason == "max_tokens":
        text += "\n\n[[HARNESS NOTE: response was cut off by max_tokens -- likely missing its final answer, not a reasoning failure]]"
    return text

# ---------------- Main evaluation loop ----------------
def run_evaluation(problems, model_name, use_mock, sleep_s=0.0):
    records = []
    for p in problems:
        prompt = PROMPT_TEMPLATE.format(problem=p["problem"])
        if use_mock:
            raw_response = call_mock_model(prompt, p)
        else:
            raw_response = call_anthropic_model(prompt, p, model=model_name)
        predicted = extract_boxed_answer(raw_response)
        correct = grade(predicted, p["answer"])
        records.append({
            **p,
            "predicted": predicted,
            "correct": correct,
            "raw_response": raw_response,
        })
        if sleep_s:
            time.sleep(sleep_s)
    return pd.DataFrame(records)

def summarize(df: pd.DataFrame):
    overall = df["correct"].mean()
    by_cat = df.groupby("category")["correct"].mean().sort_values()
    by_diff = df.groupby("difficulty")["correct"].mean()
    print(f"Overall accuracy: {overall:.1%}  (n={len(df)})")
    print("\nBy category:")
    print((by_cat * 100).round(1).astype(str) + "%")
    print("\nBy difficulty:")
    print((by_diff * 100).round(1).astype(str) + "%")
    return overall, by_cat, by_diff

def plot_results(df, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    cat_acc = df.groupby("category")["correct"].mean().sort_values()
    axes[0].barh(cat_acc.index, cat_acc.values * 100, color="#2b6cb0")
    axes[0].set_xlabel("Accuracy (%)"); axes[0].set_xlim(0, 100)
    axes[0].set_title("(a) Accuracy by category")
    axes[0].grid(alpha=0.3, axis='x')

    diff_acc = df.groupby("difficulty")["correct"].mean()
    axes[1].bar(diff_acc.index.astype(str), diff_acc.values * 100, color="#c05621")
    axes[1].set_xlabel("Difficulty level"); axes[1].set_ylabel("Accuracy (%)")
    axes[1].set_ylim(0, 100)
    axes[1].set_title("(b) Accuracy by difficulty")
    axes[1].grid(alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved figure to {out_path}")

def failure_report(df: pd.DataFrame, out_path):
    fails = df[~df["correct"]].copy()
    with open(out_path, 'w') as f:
        f.write(f"FAILURE ANALYSIS WORKSHEET  ({len(fails)} / {len(df)} problems failed)\n")
        f.write("="*70 + "\n\n")
        f.write("For each failed problem below, fill in:\n")
        f.write("  (1) What mathematical step did the model get wrong?\n")
        f.write("  (2) Is this a *reasoning* error (wrong method) or a\n")
        f.write("      *computation* error (right method, arithmetic slip)?\n")
        f.write("  (3) Does this problem's skill_tag suggest a pattern across\n")
        f.write("      the failures (e.g. all failures involve multi-step\n")
        f.write("      case analysis, or all involve a specific identity)?\n\n")
        for _, row in fails.iterrows():
            f.write(f"[{row['id']}] {row['category']} / difficulty {row['difficulty']} "
                     f"/ skill: {row['skill_tag']}\n")
            f.write(f"Problem: {row['problem']}\n")
            f.write(f"Gold answer: {row['answer']}   Model answer: {row['predicted']}\n")
            f.write(f"Model reasoning:\n{row['raw_response']}\n")
            f.write("Your analysis: ____________________________________________\n")
            f.write("-"*70 + "\n\n")
    print(f"Saved failure-analysis worksheet to {out_path} ({len(fails)} entries)")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--mock", action="store_true", help="force mock model even if API key is set")
    ap.add_argument("--problems", default="problems.json", help="path to problem bank JSON file")
    ap.add_argument("--out-prefix", default="", help="prefix for output filenames, e.g. 'hard_' -> hard_eval_results.jsonl")
    args = ap.parse_args()

    problems = json.load(open(args.problems))[:args.n]
    use_mock = args.mock or ("ANTHROPIC_API_KEY" not in os.environ)
    if use_mock:
        print(">>> No ANTHROPIC_API_KEY found (or --mock passed): running with MOCK model.")
        print(">>> This validates the pipeline only -- results are NOT real evaluation data.\n")

    df = run_evaluation(problems, args.model, use_mock)
    df.to_json(f"{args.out_prefix}eval_results.jsonl", orient="records", lines=True)
    summarize(df)
    plot_results(df, f"{args.out_prefix}fig_accuracy.png")
    failure_report(df, f"{args.out_prefix}failure_analysis.txt")
