"""
Retrieval Evaluation -- Precision@1, Precision@3, Precision@8, MRR.
Uses an LLM-as-relevance-judge to avoid manual annotation.

For each test query, the top-8 Cortex Search results are shown to
llama3.1-70b which rates each chunk as RELEVANT or NOT_RELEVANT
given the query. This gives automated Precision@K.

Outputs: results/retrieval_eval.json
"""

import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.snowflake_client import execute_scalar

RESULTS_DIR    = os.path.join(os.path.dirname(__file__), "results")
SEARCH_SERVICE = "PODCASTIQ.SEMANTIC.PODCASTIQ_SEARCH"
RETURN_COLUMNS = ["CHUNK_TEXT", "EPISODE_TITLE", "CHANNEL_NAME", "YOUTUBE_URL"]
SEARCH_LIMIT   = 8

# -- 20 test queries spanning all major topics in corpus ----------------------
TEST_QUERIES = [
    "Sam Altman on the future of OpenAI",
    "Andrew Huberman sleep optimization protocols",
    "Marc Andreessen views on software and innovation",
    "Lex Fridman discussing artificial general intelligence",
    "intermittent fasting and longevity research",
    "startup fundraising advice from founders",
    "AI safety risks and alignment",
    "crypto and blockchain future predictions",
    "cold exposure and dopamine benefits",
    "GPT models and language model capabilities",
    "exercise and cognitive performance",
    "venture capital and startup valuation",
    "Elon Musk on autonomous vehicles and Tesla",
    "mental health and meditation practices",
    "protein intake and muscle building research",
    "remote work productivity and company culture",
    "geopolitics and technology competition",
    "podcast industry growth and creator economy",
    "climate change and energy transition",
    "consciousness and neuroscience research",
]

RELEVANCE_PROMPT = """You are evaluating search results for a podcast intelligence system.

Query: "{query}"

Search result:
\"\"\"{chunk}\"\"\"

Is this search result RELEVANT to the query? A result is relevant if it contains
information that directly helps answer or explore the query topic.

Respond with exactly one word: RELEVANT or NOT_RELEVANT"""


def cortex_search(query: str) -> list[dict]:
    """Call Cortex Search via SEARCH_PREVIEW and return result rows."""
    payload = json.dumps({
        "query":   query,
        "columns": RETURN_COLUMNS,
        "limit":   SEARCH_LIMIT,
    })
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s, %s)",
        (SEARCH_SERVICE, payload),
    )
    if not raw:
        return []
    data = json.loads(raw)
    return data.get("results", [])


def safe_print(s: str):
    print(s.encode("cp1252", errors="replace").decode("cp1252"))


def judge_relevance(query: str, chunk: str) -> bool:
    verdict = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (RELEVANCE_PROMPT.format(query=query, chunk=chunk[:600]),),
    )
    return "RELEVANT" in (verdict or "").upper() and "NOT_RELEVANT" not in (verdict or "").upper()


def precision_at_k(relevance: list, k: int) -> float:
    return sum(relevance[:k]) / k if len(relevance) >= k else 0.0


def mrr(relevance: list) -> float:
    for i, r in enumerate(relevance):
        if r:
            return 1.0 / (i + 1)
    return 0.0


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("=" * 60)
    print("RETRIEVAL EVALUATION  (Precision@K + MRR)")
    print("=" * 60)

    all_results = []
    p1_scores, p3_scores, p8_scores, mrr_scores = [], [], [], []

    for i, query in enumerate(TEST_QUERIES):
        print(f"\n[{i+1:02d}/{len(TEST_QUERIES)}] {query[:60]}")
        try:
            rows = cortex_search(query)
        except Exception as e:
            print(f"  Search error: {e}")
            continue

        if not rows:
            print("  No results returned")
            continue

        relevance = []
        for row in rows:
            chunk = row.get("CHUNK_TEXT", "")
            rel = judge_relevance(query, chunk)
            relevance.append(rel)
            mark = "[Y]" if rel else "[N]"
            safe_print(f"  {mark} {str(row.get('EPISODE_TITLE',''))[:50]}")

        p1 = precision_at_k(relevance, 1)
        p3 = precision_at_k(relevance, 3)
        p8 = precision_at_k(relevance, 8)
        m  = mrr(relevance)

        p1_scores.append(p1)
        p3_scores.append(p3)
        p8_scores.append(p8)
        mrr_scores.append(m)

        print(f"  P@1={p1:.2f}  P@3={p3:.2f}  P@8={p8:.2f}  MRR={m:.2f}")
        all_results.append({
            "query":          query,
            "num_results":    len(rows),
            "relevance":      relevance,
            "precision_at_1": p1,
            "precision_at_3": p3,
            "precision_at_8": p8,
            "mrr":            m,
        })

    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0

    summary = {
        "mean_precision_at_1": avg(p1_scores),
        "mean_precision_at_3": avg(p3_scores),
        "mean_precision_at_8": avg(p8_scores),
        "mean_mrr":            avg(mrr_scores),
        "num_queries":         len(all_results),
        "per_query":           all_results,
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Mean Precision@1 : {summary['mean_precision_at_1']:.3f}")
    print(f"  Mean Precision@3 : {summary['mean_precision_at_3']:.3f}")
    print(f"  Mean Precision@8 : {summary['mean_precision_at_8']:.3f}")
    print(f"  Mean MRR         : {summary['mean_mrr']:.3f}")

    out_path = os.path.join(RESULTS_DIR, "retrieval_eval.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
