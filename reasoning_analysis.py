"""
reasoning_analysis.py
---------------------
Upgrade #1 for the AI4Math reasoning lab application: shift the project from
ANSWER-level evaluation to STEP-level reasoning analysis.

The original eval_pipeline.py answers one question: "did the model get the
final answer right?" That is exactly the "grading by the final answer" that
the target lab explicitly wants to move beyond ("teach AI to reason step by
step, not guess the answer by memorization"). This module answers a harder
and more relevant question:

    "Even when the final answer is right, is the REASONING actually valid --
     or did the model reach a correct answer through a flawed or skipped
     chain (i.e. 'got it right for the wrong reason')?"

It does this in two stages:
  1. SEGMENT the model's free-form solution into discrete reasoning steps.
  2. VERIFY each step independently, and classify the first point of failure.

Stage 2 uses a second LLM call as a "verifier" (LLM-as-judge, a standard
technique in the reasoning-evaluation literature) whose ONLY job is to check
one step's local validity. Because a no-API-key mock is included, the whole
pipeline can be validated offline before spending credits.

This directly serves the lab's stated goal: distinguishing genuine
step-by-step reasoning from answer-guessing.
"""
import json, re, os, argparse
from dataclasses import dataclass, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Stage 1: segment a free-form solution into reasoning steps
# ---------------------------------------------------------------------------
def segment_steps(solution_text: str):
    """Split a model's solution into ordered reasoning steps.

    Heuristic, transparent segmentation (no LLM needed): split on explicit
    step markers, numbered lists, or double newlines, whichever the model
    used. Kept deliberately simple and inspectable -- the point is that a
    human can audit exactly how the chain was cut.
    """
    text = solution_text.strip()
    # Prefer explicit "Step N" markers if the model used them.
    if re.search(r"(?im)^\s*\**step\s*\d+", text):
        parts = re.split(r"(?im)^\s*\**step\s*\d+\s*[:.)]?\s*\**", text)
        steps = [p.strip() for p in parts if p.strip()]
    else:
        # Split on blank lines AND on bold-markdown headings used as inline
        # section separators (e.g. "**Calculating each term:**"), which models
        # use in place of "Step N". Without this, a heading and the math after
        # it get glued into one segment, or the heading survives as its own
        # content-free "step".
        text = re.sub(r"\*\*([^*\n]{0,80}?):?\*\*", r"\n\n", text)  # headings -> breaks
        steps = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    # Drop a trailing "Final Answer: ..." line from the last step so the
    # answer itself isn't graded as a reasoning step.
    cleaned = []
    for s in steps:
        s = re.sub(r"(?is)final answer\s*:.*$", "", s).strip()
        # strip a leftover bold-header fragment like "Set up the relationship**"
        s = re.sub(r"^\s*([^\n*]{0,60}?)\*\*\s*", r"\1\n", s).strip()
        if s and not _is_structural_only(s):
            cleaned.append(s)
    return cleaned


def _is_structural_only(segment: str) -> bool:
    """True if a segment carries no verifiable mathematical content -- e.g. a
    lone Markdown heading like '## Final Calculation', a bold section label like
    '**Calculating each term:**', or a bare title. Such lines are structure, not
    reasoning steps, and must not enter step verification (an early version
    wrongly flagged them as 'skipped_step').
    """
    # Remove markdown heading marks, bold/italic markers, trailing colons, space.
    stripped = re.sub(r"[#*_`>\-:]", "", segment).strip()
    if not stripped:
        return True
    # A short line that is only words + a trailing colon/asterisks and has NO
    # math relation (=, an operator between numbers, a fraction) is a heading,
    # even if it contains an isolated digit. Require an actual math relation to
    # count as content.
    has_relation = bool(re.search(r"[=<>≤≥≡]|[0-9)]\s*[+\-*/^]\s*[0-9(]|\\d?frac|\\times|\\cdot", segment))
    if has_relation:
        return False
    # No math relation: treat short phrases (section labels) as structural.
    return len(stripped.split()) <= 8


# ---------------------------------------------------------------------------
# Stage 2: verify each step
# ---------------------------------------------------------------------------
@dataclass
class StepJudgment:
    index: int
    step_text: str
    verdict: str            # "valid" | "invalid" | "unsupported"
    error_type: Optional[str]  # e.g. "computation", "reasoning", "skipped_step", None
    note: str

VERIFIER_PROMPT = """You are checking ONE step of a mathematical solution for
local validity. You are NOT solving the whole problem. Given the problem, the
reasoning so far, and the single step to check, decide whether THIS step
follows validly from what came before.

Respond in strict JSON, no prose outside it:
{{"verdict": "valid" | "invalid" | "unsupported",
  "error_type": null | "computation" | "reasoning" | "skipped_step",
  "note": "<one short sentence>"}}

- "valid": the step is mathematically correct and follows from prior context.
- "invalid": the step contains a concrete error. Set error_type to
  "computation" (arithmetic/algebra slip) or "reasoning" (wrong method,
  invalid inference).
- "unsupported": the step jumps to a conclusion without showing why
  (set error_type to "skipped_step") -- the answer may still be right, but
  the chain has a gap.

Problem: {problem}

Reasoning so far:
{prior}

Step to check:
{step}
"""

def verify_step_mock(problem, prior, step, index):
    """Deterministic stand-in: flags a step as skipped if it contains a
    result-like '=' with no connecting words, else calls it valid. Only for
    validating the pipeline offline -- NOT a real judgment."""
    looks_like_jump = bool(re.search(r"=\s*-?\d", step)) and len(step) < 40
    if looks_like_jump:
        return StepJudgment(index, step, "unsupported", "skipped_step",
                            "[MOCK] short step with a bare result and little justification")
    return StepJudgment(index, step, "valid", None, "[MOCK] no local error detected")

def verify_step_llm(problem, prior, step, index, model="claude-sonnet-5"):
    import anthropic
    client = anthropic.Anthropic()
    prompt = VERIFIER_PROMPT.format(problem=problem, prior=prior or "(this is the first step)", step=step)
    resp = client.messages.create(model=model, max_tokens=512,
                                  messages=[{"role": "user", "content": prompt}])
    raw = "".join(b.text for b in resp.content if b.type == "text")
    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        d = json.loads(raw)
        return StepJudgment(index, step, d.get("verdict", "unsupported"),
                            d.get("error_type"), d.get("note", ""))
    except json.JSONDecodeError:
        return StepJudgment(index, step, "unsupported", None,
                            f"verifier returned unparseable output: {raw[:80]}")


# ---------------------------------------------------------------------------
# Orchestration: analyze one solution end-to-end
# ---------------------------------------------------------------------------
def analyze_solution(problem, solution_text, final_answer_correct, use_mock, model="claude-sonnet-5"):
    steps = segment_steps(solution_text)
    judgments = []
    prior_accum = []
    first_failure = None
    for i, step in enumerate(steps):
        prior = "\n".join(prior_accum)
        if use_mock:
            j = verify_step_mock(problem, prior, step, i)
        else:
            j = verify_step_llm(problem, prior, step, i, model=model)
        judgments.append(j)
        if j.verdict != "valid" and first_failure is None:
            first_failure = i
        prior_accum.append(step)

    chain_valid = all(j.verdict == "valid" for j in judgments)
    # The key diagnostic the lab cares about:
    right_answer_wrong_reasoning = final_answer_correct and not chain_valid

    return {
        "problem": problem,
        "n_steps": len(steps),
        "chain_fully_valid": chain_valid,
        "first_failure_step": first_failure,
        "final_answer_correct": final_answer_correct,
        "right_answer_wrong_reasoning": right_answer_wrong_reasoning,
        "step_judgments": [asdict(j) for j in judgments],
    }


def summarize_reasoning(analyses):
    n = len(analyses)
    n_answer_correct = sum(a["final_answer_correct"] for a in analyses)
    n_chain_valid = sum(a["chain_fully_valid"] for a in analyses)
    n_guessed = sum(a["right_answer_wrong_reasoning"] for a in analyses)
    print(f"Problems analyzed:                         {n}")
    print(f"Final answer correct:                      {n_answer_correct}/{n}")
    print(f"Reasoning chain fully valid:               {n_chain_valid}/{n}")
    print(f"Right answer BUT flawed/skipped reasoning: {n_guessed}/{n}")
    print()
    print("The gap between 'answer correct' and 'chain valid' is exactly the")
    print("quantity answer-only grading hides -- and the quantity a reasoning")
    print("lab cares about most.")
    # error-type breakdown
    from collections import Counter
    etypes = Counter()
    for a in analyses:
        for j in a["step_judgments"]:
            if j["verdict"] != "valid":
                etypes[j["error_type"] or "unclassified"] += 1
    if etypes:
        print("\nStep-level failure types across all problems:")
        for k, v in etypes.most_common():
            print(f"  {k:16s} {v}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="eval_results.jsonl",
                    help="jsonl from eval_pipeline.py (has problem, raw_response, correct)")
    ap.add_argument("--model", default="claude-sonnet-5")
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default="reasoning_analysis.jsonl")
    args = ap.parse_args()

    use_mock = args.mock or ("ANTHROPIC_API_KEY" not in os.environ)
    if use_mock:
        print(">>> Running step-verification with MOCK judge (no API key or --mock).")
        print(">>> Pipeline-validation only; verdicts are NOT real.\n")

    rows = [json.loads(l) for l in open(args.results)]
    analyses = []
    for r in rows:
        a = analyze_solution(r["problem"], r.get("raw_response", ""),
                             r.get("correct", False), use_mock, model=args.model)
        analyses.append(a)

    with open(args.out, "w") as f:
        for a in analyses:
            f.write(json.dumps(a) + "\n")
    summarize_reasoning(analyses)
    print(f"\nWrote per-step judgments to {args.out}")
