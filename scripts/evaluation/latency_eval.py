"""
Latency Evaluation — measures end-to-end response time for all 8 agent types.

Each agent type is called 3 times; reports mean and p95 latency.
Saves per-agent timing distributions to results/latency_eval.json.
"""

import os, sys, json, time, statistics
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.graph import run as agent_run

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# -- 3 representative queries per agent type -----------------------------------
TEST_QUERIES = {
    "SEARCH": [
        "What did Sam Altman say about GPT-5?",
        "Find clips where Huberman discusses cold exposure",
        "What did Lex Fridman say about consciousness?",
    ],
    "SUMMARIZE": [
        "What are the best strategies for building a startup?",
        "What do experts say about sleep and cognitive performance?",
        "What is the consensus on AI safety risks?",
    ],
    "RECOMMEND": [
        "Recommend episodes about longevity and health",
        "What should I watch about AI and the future?",
        "Suggest episodes with Sam Altman",
    ],
    "COMPARE": [
        "Compare Sam Altman and Elon Musk on AI",
        "How do Lex Fridman and Andrew Huberman differ on sleep?",
        "Compare views on crypto between different podcasters",
    ],
    "TEMPORAL": [
        "How has opinion on AGI changed over time?",
        "How has the discourse on remote work shifted?",
        "What claims about AI have been revised over the years?",
    ],
    "FACTCHECK": [
        "Fact check: GPT-5 was released in 2024",
        "Is it true that Sam Altman was fired from OpenAI?",
        "Verify: OpenAI is valued at over $80 billion",
    ],
    "INSIGHT": [
        "Which podcast channel has the most contradicted claims?",
        "What are the most debated topics across all podcasts?",
        "Which speakers make the most predictions?",
    ],
    "GRAPH": [
        "Who has Sam Altman appeared with across podcasts?",
        "Which guests appeared on multiple shows?",
        "Show Lex Fridman's guest network",
    ],
}


def run_timed(query: str) -> tuple[float, bool]:
    """Returns (elapsed_seconds, success)."""
    t0 = time.perf_counter()
    try:
        result = agent_run(query)
        elapsed = time.perf_counter() - t0
        # Consider success if we got some response content
        ok = bool(
            result.get("summary") or
            result.get("search_results") or
            result.get("graph_results") or
            result.get("recommendations") or
            result.get("factcheck_result")
        )
        return elapsed, ok
    except Exception as e:
        elapsed = time.perf_counter() - t0
        print(f"    Error: {e}")
        return elapsed, False


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = int(0.95 * len(sorted_v))
    return sorted_v[min(idx, len(sorted_v) - 1)]


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("=" * 60)
    print("LATENCY EVALUATION  (3 runs per agent type)")
    print("=" * 60)

    results = {}
    overall_latencies = []

    for agent_type, queries in TEST_QUERIES.items():
        print(f"\n-- {agent_type} --")
        latencies = []
        successes = 0

        for i, query in enumerate(queries):
            print(f"  [{i+1}/{len(queries)}] {query[:55]}", end="", flush=True)
            elapsed, ok = run_timed(query)
            latencies.append(elapsed)
            if ok:
                successes += 1
            mark = "[Y]" if ok else "[N]"
            print(f"  {elapsed:.2f}s [{mark}]")

        mean_lat = statistics.mean(latencies) if latencies else 0
        p95_lat  = p95(latencies)
        overall_latencies.extend(latencies)

        results[agent_type] = {
            "queries_run":   len(queries),
            "successes":     successes,
            "mean_s":        round(mean_lat, 3),
            "p95_s":         round(p95_lat, 3),
            "min_s":         round(min(latencies), 3) if latencies else 0,
            "max_s":         round(max(latencies), 3) if latencies else 0,
            "raw_s":         [round(x, 3) for x in latencies],
        }
        print(f"  -> mean={mean_lat:.2f}s  p95={p95_lat:.2f}s  "
              f"success={successes}/{len(queries)}")

    # -- Overall summary --------------------------------------------------------
    overall_mean = statistics.mean(overall_latencies) if overall_latencies else 0
    overall_p95  = p95(overall_latencies)

    summary = {
        "overall_mean_s":  round(overall_mean, 3),
        "overall_p95_s":   round(overall_p95, 3),
        "total_queries":   len(overall_latencies),
        "per_agent":       results,
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  Overall mean latency : {overall_mean:.2f}s")
    print(f"  Overall p95  latency : {overall_p95:.2f}s")
    print()
    print(f"  {'Agent':<12}  {'Mean':>8}  {'p95':>8}  {'Success':>8}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*8}")
    for agent_type, v in results.items():
        print(f"  {agent_type:<12}  {v['mean_s']:>7.2f}s  {v['p95_s']:>7.2f}s  "
              f"  {v['successes']}/{v['queries_run']}")

    out_path = os.path.join(RESULTS_DIR, "latency_eval.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
