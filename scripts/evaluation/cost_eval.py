"""
Cost Evaluation — estimates Snowflake Cortex token usage and dollar cost per agent type.

Methodology:
- One representative query per agent type is run through the full pipeline
- Token counts come from actual Snowflake QUERY_HISTORY (CREDITS_USED_CLOUD_SERVICES)
  and estimated from response lengths where billing data isn't accessible
- Cortex LLM pricing (as of 2025): llama3.1-70b ~$0.00060/1k tokens
                                   llama3.1-8b  ~$0.00006/1k tokens
                                   Arctic-embed ~$0.00010/1k tokens

Outputs: results/cost_eval.json
"""

import os, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.graph import run as agent_run
from langgraph_agents.snowflake_client import execute

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# -- Cortex LLM pricing per 1k tokens (approximate, Jan 2026) -----------------
PRICE_PER_1K = {
    "llama3.1-70b":  0.00060,
    "llama3.1-8b":   0.00006,
    "llama3.1-405b": 0.00350,
    "arctic-embed":  0.00010,
}

# -- Default model used per agent (from agent source files) -------------------
AGENT_MODELS = {
    "SEARCH":    [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval")],
    "SUMMARIZE": [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval"), ("llama3.1-70b", "summarization")],
    "RECOMMEND": [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval"), ("llama3.1-70b", "recommendation")],
    "COMPARE":   [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval"), ("llama3.1-70b", "comparison")],
    "TEMPORAL":  [("llama3.1-8b", "routing"), ("llama3.1-8b", "keyword-extract"), ("llama3.1-70b", "temporal-summary")],
    "FACTCHECK": [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval"), ("llama3.1-70b", "fact-check")],
    "INSIGHT":   [("llama3.1-8b", "routing"), ("llama3.1-70b", "insight-summary")],
    "GRAPH":     [("llama3.1-8b", "routing"), ("arctic-embed", "retrieval")],
}

# -- Representative queries (one per type) -------------------------------------
SAMPLE_QUERIES = {
    "SEARCH":    "What did Sam Altman say about GPT-5?",
    "SUMMARIZE": "What are the best strategies for building a startup?",
    "RECOMMEND": "Recommend episodes about longevity and health",
    "COMPARE":   "Compare Sam Altman and Elon Musk on AI",
    "TEMPORAL":  "How has opinion on AGI changed over time?",
    "FACTCHECK": "Fact check: GPT-5 was released in 2024",
    "INSIGHT":   "Which podcast channel has the most contradicted claims?",
    "GRAPH":     "Who has Sam Altman appeared with across podcasts?",
}

# -- Typical token budgets per step (estimated from prompt templates) ----------
# (input_tokens, output_tokens) per LLM call
TOKEN_BUDGETS = {
    "routing":          (200,   10),   # Short prompt, single word output
    "retrieval":        (50,    0),    # Embedding only, no generation
    "summarization":    (3000,  600),  # 5 chunks × 400 tokens + instructions
    "recommendation":   (2000,  400),  # Episode metadata + instructions
    "comparison":       (3000,  500),  # Claims from 2 speakers
    "temporal-summary": (1500,  400),  # Evolution pairs + instructions
    "fact-check":       (2000,  300),  # Claim + Brave results + instructions
    "insight-summary":  (1500,  400),  # Stats table + instructions
    "keyword-extract":  (100,    20),  # Extract 2-3 keywords
}


def estimate_cost_static(agent_type: str) -> dict:
    """Compute cost from hardcoded token budgets (no live call needed)."""
    total_input  = 0
    total_output = 0
    total_cost   = 0.0
    breakdown    = []

    for model, step in AGENT_MODELS[agent_type]:
        budget = TOKEN_BUDGETS.get(step, (500, 200))
        inp, out = budget
        price = PRICE_PER_1K.get(model, 0.0001)
        cost  = (inp + out) / 1000 * price
        total_input  += inp
        total_output += out
        total_cost   += cost
        breakdown.append({
            "step":            step,
            "model":           model,
            "input_tokens":    inp,
            "output_tokens":   out,
            "cost_usd":        round(cost, 6),
        })

    return {
        "total_input_tokens":  total_input,
        "total_output_tokens": total_output,
        "total_tokens":        total_input + total_output,
        "total_cost_usd":      round(total_cost, 6),
        "breakdown":           breakdown,
    }


def measure_actual_response_tokens(query: str) -> dict:
    """Run one query and count rough output size to validate estimates."""
    t0 = time.perf_counter()
    try:
        result = agent_run(query)
        elapsed = time.perf_counter() - t0

        # Approximate output token count from response length
        summary  = result.get("summary", "")
        chunks   = result.get("search_results", [])
        actual_output_chars = len(summary) + sum(len(str(c)) for c in chunks[:3])
        # ~4 chars per token is a rough approximation
        approx_output_tokens = actual_output_chars // 4

        return {
            "elapsed_s":            round(elapsed, 2),
            "approx_output_tokens": approx_output_tokens,
            "summary_chars":        len(summary),
            "num_chunks_returned":  len(chunks),
        }
    except Exception as e:
        return {"error": str(e), "elapsed_s": round(time.perf_counter() - t0, 2)}


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("=" * 60)
    print("COST EVALUATION  (static model + live response validation)")
    print("=" * 60)

    all_results = {}
    total_cost_usd = 0.0

    for agent_type, query in SAMPLE_QUERIES.items():
        print(f"\n-- {agent_type} --")
        print(f"  Query: {query[:60]}")

        # Static cost estimate from token budgets
        static = estimate_cost_static(agent_type)

        # Live run for output size validation
        print(f"  Running live query...", end="", flush=True)
        live = measure_actual_response_tokens(query)
        print(f" {live.get('elapsed_s', '?')}s")

        total_cost_usd += static["total_cost_usd"]

        all_results[agent_type] = {
            "query":        query,
            "static_model_estimate": static,
            "live_validation":       live,
        }

        print(f"  Tokens (est): {static['total_input_tokens']} in + "
              f"{static['total_output_tokens']} out = {static['total_tokens']} total")
        print(f"  Cost (est):   ${static['total_cost_usd']:.6f}")
        for step in static["breakdown"]:
            print(f"    {step['step']:20s}  {step['model']:20s}  "
                  f"{step['input_tokens']:>5} in  {step['output_tokens']:>4} out  "
                  f"${step['cost_usd']:.6f}")

    # -- Aggregate --------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print(f"  {'Agent':<12}  {'Tokens':>8}  {'Cost (USD)':>12}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*12}")
    for agent_type, v in all_results.items():
        est = v["static_model_estimate"]
        print(f"  {agent_type:<12}  {est['total_tokens']:>8}  ${est['total_cost_usd']:>11.6f}")
    print(f"  {'-'*12}  {'-'*8}  {'-'*12}")
    print(f"  {'TOTAL':<12}  {'':>8}  ${total_cost_usd:>11.6f}")

    # Estimate cost per 1000 queries (assuming uniform distribution across types)
    cost_per_query = total_cost_usd / len(SAMPLE_QUERIES)
    cost_per_1k    = cost_per_query * 1000
    print(f"\n  Avg cost/query : ${cost_per_query:.6f}")
    print(f"  Projected /1k  : ${cost_per_1k:.4f}")

    output = {
        "per_agent":           all_results,
        "total_cost_usd":      round(total_cost_usd, 6),
        "avg_cost_per_query":  round(cost_per_query, 6),
        "projected_per_1k":    round(cost_per_1k, 4),
        "pricing_model":       PRICE_PER_1K,
        "note": (
            "Token counts are estimated from prompt templates. "
            "Actual Cortex billing depends on model-specific tokenization. "
            "See Snowflake ACCOUNT_USAGE.QUERY_HISTORY for exact credit usage."
        ),
    }

    out_path = os.path.join(RESULTS_DIR, "cost_eval.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
