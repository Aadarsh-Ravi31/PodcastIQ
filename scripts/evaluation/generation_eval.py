"""
Generation Quality Evaluation — ROUGE, BERTScore, dual LLM-as-judge.

Approach:
- Run 10 SUMMARIZE queries through the full agent pipeline
- ROUGE + BERTScore: compare generated summary against the retrieved
  chunks concatenated (extractive baseline — what the LLM was given)
- LLM-as-judge (dual):
    Judge 1: llama3.1-70b via Snowflake Cortex  (same model family as generator)
    Judge 2: gpt-4o via OpenAI API              (independent cross-validation)
  Both score Faithfulness, Relevance, Groundedness (1-5 scale).
  Agreement between judges increases confidence in the scores.

Outputs: results/generation_eval.json

Requirements: pip install rouge-score bert-score openai
"""

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.graph import run as agent_run
from langgraph_agents.snowflake_client import execute_scalar
from dotenv import load_dotenv
load_dotenv()

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ── 10 SUMMARIZE queries ──────────────────────────────────────────────────────
TEST_QUERIES = [
    "What are the best strategies for building a startup?",
    "What do experts say about sleep and cognitive performance?",
    "What is the consensus on AI safety risks?",
    "How does intermittent fasting affect longevity?",
    "What advice do founders give about hiring and company culture?",
    "What do podcasters say about the future of work and remote teams?",
    "What are the main arguments about crypto and blockchain?",
    "How do experts approach mental health and stress management?",
    "What do health experts say about exercise and brain health?",
    "What are common views on venture capital and startup valuations?",
]

# ── Shared judge prompt ───────────────────────────────────────────────────────
JUDGE_PROMPT = """You are an expert evaluator for an AI podcast intelligence system.
Evaluate the generated response against the source context on three dimensions.

User Query: "{query}"

Source Context (retrieved podcast chunks):
{context}

Generated Response:
{response}

Score each dimension from 1 to 5:
- Faithfulness (1-5): Does the response only contain claims supported by the source context?
  5 = every claim is directly supported, 1 = many claims contradict or go beyond the context.
- Relevance (1-5): Does the response directly address the user's query?
  5 = directly and completely answers the query, 1 = barely related to the query.
- Groundedness (1-5): Does the response correctly represent the podcast speakers' actual positions?
  5 = accurately represents what was said, 1 = distorts or misattributes positions.

Respond with ONLY valid JSON in this format:
{{"faithfulness": <1-5>, "relevance": <1-5>, "groundedness": <1-5>, "reasoning": "<one sentence>"}}"""


# ── Judge 1: llama3.1-70b via Snowflake Cortex ────────────────────────────────
def llm_judge_llama(query: str, context: str, response: str) -> dict:
    prompt = JUDGE_PROMPT.format(
        query=query,
        context=context[:2000],
        response=response[:1000],
    )
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```"))
    try:
        return json.loads(raw)
    except Exception:
        return {"faithfulness": None, "relevance": None, "groundedness": None, "reasoning": "parse error"}


# ── Judge 2: gpt-4o via OpenAI API ───────────────────────────────────────────
def llm_judge_gpt4o(query: str, context: str, response: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("#"):
        return {"faithfulness": None, "relevance": None, "groundedness": None,
                "reasoning": "OPENAI_API_KEY not set — skipped"}
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = JUDGE_PROMPT.format(
            query=query,
            context=context[:2000],
            response=response[:1000],
        )
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or ""
        return json.loads(raw)
    except Exception as e:
        return {"faithfulness": None, "relevance": None, "groundedness": None,
                "reasoning": f"OpenAI error: {str(e)[:80]}"}


# ── ROUGE ─────────────────────────────────────────────────────────────────────
def compute_rouge(hypothesis: str, reference: str) -> dict:
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
        scores = scorer.score(reference, hypothesis)
        return {
            "rouge1_f": round(scores["rouge1"].fmeasure, 4),
            "rouge2_f": round(scores["rouge2"].fmeasure, 4),
            "rougeL_f": round(scores["rougeL"].fmeasure, 4),
        }
    except ImportError:
        print("  [WARN] rouge-score not installed. Run: pip install rouge-score")
        return {"rouge1_f": None, "rouge2_f": None, "rougeL_f": None}


# ── BERTScore ─────────────────────────────────────────────────────────────────
def compute_bertscore(hypothesis: str, reference: str) -> dict:
    try:
        from bert_score import score as bs_score
        P, R, F1 = bs_score([hypothesis], [reference], lang="en", verbose=False)
        return {
            "bertscore_precision": round(P[0].item(), 4),
            "bertscore_recall":    round(R[0].item(), 4),
            "bertscore_f1":        round(F1[0].item(), 4),
        }
    except ImportError:
        print("  [WARN] bert-score not installed. Run: pip install bert-score")
        return {"bertscore_precision": None, "bertscore_recall": None, "bertscore_f1": None}


# ── Agreement helper ──────────────────────────────────────────────────────────
def judge_agreement(j1: dict, j2: dict) -> dict:
    """Compute mean absolute difference between two judges across all dimensions."""
    dims = ["faithfulness", "relevance", "groundedness"]
    diffs = []
    for d in dims:
        v1, v2 = j1.get(d), j2.get(d)
        if v1 is not None and v2 is not None:
            diffs.append(abs(v1 - v2))
    mean_diff = round(sum(diffs) / len(diffs), 3) if diffs else None
    agreement  = "HIGH" if mean_diff is not None and mean_diff <= 0.5 else \
                 "MODERATE" if mean_diff is not None and mean_diff <= 1.0 else "LOW"
    return {"mean_absolute_diff": mean_diff, "agreement_level": agreement}


def sp(s):
    print(str(s).encode("cp1252", errors="replace").decode("cp1252"))


def main():
    print("=" * 65)
    print("GENERATION QUALITY EVALUATION")
    print("ROUGE + BERTScore + Dual LLM-as-judge (llama3.1-70b vs gpt-4o)")
    print("=" * 65)

    openai_key = os.getenv("OPENAI_API_KEY", "")
    gpt4o_available = bool(openai_key and not openai_key.startswith("#"))
    if gpt4o_available:
        print("  GPT-4o judge: ENABLED")
    else:
        print("  GPT-4o judge: DISABLED (set OPENAI_API_KEY in .env)")

    all_results = []
    rouge1, rouge2, rougeL, bs_f1 = [], [], [], []
    llama_faith, llama_relev, llama_ground = [], [], []
    gpt_faith,   gpt_relev,   gpt_ground   = [], [], []
    agreements = []

    for i, query in enumerate(TEST_QUERIES):
        print(f"\n[{i+1:02d}/{len(TEST_QUERIES)}] {query[:65]}")

        try:
            result = agent_run(query)
        except Exception as e:
            print(f"  Agent error: {e}")
            continue

        summary = result.get("summary", "")
        search_results = result.get("search_results", [])

        if not summary:
            print("  Empty summary -- skipping")
            continue

        # Reference = concatenated retrieved chunks (extractive baseline)
        reference = " ".join(
            str(r.get("CHUNK_TEXT") or r.get("chunk_text", ""))[:400]
            for r in search_results[:5]
        )
        if not reference:
            print("  No context chunks -- skipping ROUGE/BERTScore")
            reference = query

        # ROUGE
        rouge = compute_rouge(summary, reference)
        if rouge["rouge1_f"] is not None:
            rouge1.append(rouge["rouge1_f"])
            rouge2.append(rouge["rouge2_f"])
            rougeL.append(rouge["rougeL_f"])

        # BERTScore
        bs = compute_bertscore(summary, reference)
        if bs["bertscore_f1"] is not None:
            bs_f1.append(bs["bertscore_f1"])

        # Judge 1: llama3.1-70b
        print("  Judge 1: llama3.1-70b...")
        j_llama = llm_judge_llama(query, reference, summary)
        if j_llama.get("faithfulness"):
            llama_faith.append(j_llama["faithfulness"])
            llama_relev.append(j_llama["relevance"])
            llama_ground.append(j_llama["groundedness"])

        # Judge 2: gpt-4o
        print("  Judge 2: gpt-4o...")
        j_gpt = llm_judge_gpt4o(query, reference, summary)
        if j_gpt.get("faithfulness"):
            gpt_faith.append(j_gpt["faithfulness"])
            gpt_relev.append(j_gpt["relevance"])
            gpt_ground.append(j_gpt["groundedness"])

        # Agreement
        agree = judge_agreement(j_llama, j_gpt)
        if agree["mean_absolute_diff"] is not None:
            agreements.append(agree["mean_absolute_diff"])

        sp(f"  ROUGE-1={rouge.get('rouge1_f','N/A')}  ROUGE-2={rouge.get('rouge2_f','N/A')}  BERTScore-F1={bs.get('bertscore_f1','N/A')}")
        sp(f"  llama  -> Faithfulness={j_llama.get('faithfulness')}  Relevance={j_llama.get('relevance')}  Groundedness={j_llama.get('groundedness')}")
        sp(f"  gpt-4o -> Faithfulness={j_gpt.get('faithfulness')}  Relevance={j_gpt.get('relevance')}  Groundedness={j_gpt.get('groundedness')}")
        sp(f"  Agreement: {agree['agreement_level']} (mean diff={agree['mean_absolute_diff']})")
        sp(f"  llama note : {j_llama.get('reasoning','')}")
        sp(f"  gpt-4o note: {j_gpt.get('reasoning','')}")

        all_results.append({
            "query":       query,
            "summary_len": len(summary),
            "rouge":       rouge,
            "bertscore":   bs,
            "llama_judge": j_llama,
            "gpt4o_judge": j_gpt,
            "agreement":   agree,
        })

    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else None

    summary_stats = {
        "num_queries":              len(all_results),
        "mean_rouge1_f":            avg(rouge1),
        "mean_rouge2_f":            avg(rouge2),
        "mean_rougeL_f":            avg(rougeL),
        "mean_bertscore_f1":        avg(bs_f1),
        # llama judge averages
        "llama_mean_faithfulness":  avg(llama_faith),
        "llama_mean_relevance":     avg(llama_relev),
        "llama_mean_groundedness":  avg(llama_ground),
        # gpt-4o judge averages
        "gpt4o_mean_faithfulness":  avg(gpt_faith),
        "gpt4o_mean_relevance":     avg(gpt_relev),
        "gpt4o_mean_groundedness":  avg(gpt_ground),
        # cross-judge agreement
        "mean_judge_agreement_diff": avg(agreements),
        "per_query":                all_results,
    }

    print("\n" + "=" * 65)
    print("SUMMARY")
    print(f"  ROUGE-1 F1          : {summary_stats['mean_rouge1_f']}")
    print(f"  ROUGE-2 F1          : {summary_stats['mean_rouge2_f']}")
    print(f"  ROUGE-L F1          : {summary_stats['mean_rougeL_f']}")
    print(f"  BERTScore F1        : {summary_stats['mean_bertscore_f1']}")
    print()
    print(f"  {'Metric':<20} {'llama-70b':>10} {'gpt-4o':>10}")
    print(f"  {'-'*42}")
    print(f"  {'Faithfulness':<20} {str(summary_stats['llama_mean_faithfulness'] or 'N/A'):>10} {str(summary_stats['gpt4o_mean_faithfulness'] or 'N/A'):>10}")
    print(f"  {'Relevance':<20} {str(summary_stats['llama_mean_relevance'] or 'N/A'):>10} {str(summary_stats['gpt4o_mean_relevance'] or 'N/A'):>10}")
    print(f"  {'Groundedness':<20} {str(summary_stats['llama_mean_groundedness'] or 'N/A'):>10} {str(summary_stats['gpt4o_mean_groundedness'] or 'N/A'):>10}")
    print()
    print(f"  Mean judge agreement diff: {summary_stats['mean_judge_agreement_diff']} (lower = more agreement)")

    out_path = os.path.join(RESULTS_DIR, "generation_eval.json")
    with open(out_path, "w") as f:
        json.dump(summary_stats, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
