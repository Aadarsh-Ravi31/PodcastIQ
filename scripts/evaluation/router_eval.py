"""
Router Evaluation — measures classification accuracy of the Router Agent.
Also runs ablation: llama3.1-8b (current) vs llama3.1-70b.

Outputs: results/router_eval.json
"""

import os, sys, json, time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.snowflake_client import execute_scalar

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ── Test set: 6 queries per route type (48 total) ─────────────────────────────
TEST_QUERIES = [
    # SEARCH
    ("Find clips where Sam Altman talks about GPT-5",                       "SEARCH"),
    ("What did Lex Fridman say about consciousness?",                       "SEARCH"),
    ("Show me moments where Huberman discusses cold exposure",              "SEARCH"),
    ("Find quotes about AI alignment from podcast episodes",                "SEARCH"),
    ("What did Marc Andreessen say about software eating the world?",       "SEARCH"),
    ("Find clips about longevity research from FoundMyFitness",             "SEARCH"),
    # SUMMARIZE
    ("What are the best strategies for building a startup?",                "SUMMARIZE"),
    ("What do experts say about intermittent fasting?",                     "SUMMARIZE"),
    ("How does sleep affect cognitive performance according to podcasts?",   "SUMMARIZE"),
    ("What is the consensus on AI safety across podcasts?",                 "SUMMARIZE"),
    ("Explain the main arguments for and against crypto",                   "SUMMARIZE"),
    ("What advice do successful founders give about hiring?",               "SUMMARIZE"),
    # RECOMMEND
    ("Recommend episodes about longevity and health",                       "RECOMMEND"),
    ("What should I watch about AI and the future?",                        "RECOMMEND"),
    ("Suggest episodes with Sam Altman",                                    "RECOMMEND"),
    ("Show me the best episodes from Huberman Lab",                         "RECOMMEND"),
    ("What podcast episodes should I listen to about startups?",            "RECOMMEND"),
    ("Recommend something from the Lex Fridman podcast",                    "RECOMMEND"),
    # COMPARE
    ("Compare Sam Altman and Elon Musk on AI",                              "COMPARE"),
    ("How do Lex Fridman and Andrew Huberman differ on sleep?",             "COMPARE"),
    ("Compare a16z and All-In Podcast on startup advice",                   "COMPARE"),
    ("What are the differences between Peter Thiel and Marc Andreessen on startups?", "COMPARE"),
    ("Compare views of Sam Altman vs Demis Hassabis on AGI",                "COMPARE"),
    ("How do different podcasters disagree on crypto?",                     "COMPARE"),
    # TEMPORAL
    ("How has opinion on AGI changed over time?",                           "TEMPORAL"),
    ("Who changed their mind about crypto?",                                "TEMPORAL"),
    ("How has Marc Andreessen evolved his views on innovation?",            "TEMPORAL"),
    ("Show contradicted predictions from 2022",                             "TEMPORAL"),
    ("What claims about AI have been revised over the years?",              "TEMPORAL"),
    ("How has the discourse on remote work shifted?",                       "TEMPORAL"),
    # FACTCHECK
    ("Fact check: GPT-5 was released in 2024",                             "FACTCHECK"),
    ("Is it true that Sam Altman was fired from OpenAI?",                   "FACTCHECK"),
    ("Fact check: Intermittent fasting reverses aging",                     "FACTCHECK"),
    ("Verify: OpenAI is valued at over $80 billion",                        "FACTCHECK"),
    ("Did Elon Musk say AGI will arrive by 2025?",                          "FACTCHECK"),
    ("Fact check: Andrew Huberman claimed cold showers boost testosterone", "FACTCHECK"),
    # INSIGHT
    ("Which podcast channel has the most contradicted claims?",             "INSIGHT"),
    ("What are the most debated topics across all podcasts?",               "INSIGHT"),
    ("Give me a credibility report on Huberman Lab",                        "INSIGHT"),
    ("Which speakers make the most predictions?",                           "INSIGHT"),
    ("What topics does the All-In Podcast cover most?",                     "INSIGHT"),
    ("Show me statistics about claim types across channels",                "INSIGHT"),
    # GRAPH
    ("Who has Sam Altman appeared with across podcasts?",                   "GRAPH"),
    ("Which guests appeared on multiple shows?",                            "GRAPH"),
    ("Show Lex Fridman's guest network",                                    "GRAPH"),
    ("Who discussed AI safety across different podcasts?",                  "GRAPH"),
    ("Which channels have the most shared guests?",                         "GRAPH"),
    ("Find all people connected to Marc Andreessen in podcasts",            "GRAPH"),
]

VALID_TYPES = {"SEARCH", "SUMMARIZE", "COMPARE", "RECOMMEND", "GRAPH",
               "TEMPORAL", "INSIGHT", "FACTCHECK"}

ROUTING_PROMPT = """You are a query classifier for a podcast intelligence system.

Classify the user's query into exactly ONE of these types:

- SUMMARIZE  : User wants to LEARN about a topic — knowledge/information questions.
- SEARCH     : User wants specific clips, quotes, or moments about a topic.
- RECOMMEND  : User explicitly wants episode/show SUGGESTIONS. Must contain words like: recommend, suggest, watch, listen, episodes.
- COMPARE    : Compare viewpoints of two specific people or channels on a topic.
- INSIGHT    : Meta-analysis about channels, speakers, or statistics across the corpus.
- GRAPH      : Questions about relationships, appearances, networks between people/topics.
- TEMPORAL   : How claims or opinions have evolved or changed over time.
- FACTCHECK  : Verify whether a specific claim is true, false, or outdated.

IMPORTANT: "What are strategies/tips/advice about X?" -> SUMMARIZE
           "Recommend/suggest/show me episodes about X" -> RECOMMEND

Respond with ONLY the type word — no explanation, no punctuation.

Query: {query}"""


def classify(query: str, model: str) -> str:
    raw = execute_scalar(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{model}', %s)",
        (ROUTING_PROMPT.format(query=query),),
    )
    result = (raw or "SEARCH").strip().upper()
    return result if result in VALID_TYPES else "SEARCH"


def run_eval(model: str) -> dict:
    correct = 0
    per_type = defaultdict(lambda: {"correct": 0, "total": 0, "wrong_as": defaultdict(int)})

    predictions = []
    for query, expected in TEST_QUERIES:
        predicted = classify(query, model)
        ok = predicted == expected
        if ok:
            correct += 1
        per_type[expected]["total"] += 1
        if ok:
            per_type[expected]["correct"] += 1
        else:
            per_type[expected]["wrong_as"][predicted] += 1
        predictions.append({"query": query, "expected": expected,
                             "predicted": predicted, "correct": ok})

    accuracy = correct / len(TEST_QUERIES)
    per_type_summary = {
        t: {
            "accuracy": v["correct"] / v["total"],
            "correct": v["correct"],
            "total": v["total"],
            "common_errors": dict(v["wrong_as"]),
        }
        for t, v in per_type.items()
    }
    return {
        "model": model,
        "overall_accuracy": round(accuracy, 4),
        "correct": correct,
        "total": len(TEST_QUERIES),
        "per_type": per_type_summary,
        "predictions": predictions,
    }


def main():
    print("=" * 60)
    print("ROUTER EVALUATION")
    print("=" * 60)

    results = {}

    # ── Primary model: llama3.1-8b ─────────────────────────────────────────────
    print(f"\nRunning with llama3.1-8b ({len(TEST_QUERIES)} queries)...")
    t0 = time.time()
    results["llama3.1-8b"] = run_eval("llama3.1-8b")
    elapsed = time.time() - t0
    r = results["llama3.1-8b"]
    print(f"  Overall accuracy: {r['overall_accuracy']:.1%}  ({r['correct']}/{r['total']})  [{elapsed:.1f}s]")
    for t, v in sorted(r["per_type"].items()):
        print(f"  {t:12s}  {v['accuracy']:.1%}  ({v['correct']}/{v['total']})", end="")
        if v["common_errors"]:
            print(f"  — errors: {dict(v['common_errors'])}", end="")
        print()

    # ── Ablation: llama3.1-70b ─────────────────────────────────────────────────
    print(f"\nAblation — llama3.1-70b ({len(TEST_QUERIES)} queries)...")
    t0 = time.time()
    results["llama3.1-70b"] = run_eval("llama3.1-70b")
    elapsed = time.time() - t0
    r70 = results["llama3.1-70b"]
    print(f"  Overall accuracy: {r70['overall_accuracy']:.1%}  ({r70['correct']}/{r70['total']})  [{elapsed:.1f}s]")
    for t, v in sorted(r70["per_type"].items()):
        print(f"  {t:12s}  {v['accuracy']:.1%}  ({v['correct']}/{v['total']})")

    # ── Ablation summary ───────────────────────────────────────────────────────
    delta = r70["overall_accuracy"] - results["llama3.1-8b"]["overall_accuracy"]
    print(f"\nAblation result: 70b improves accuracy by {delta:+.1%} over 8b")
    results["ablation_delta"] = round(delta, 4)

    out_path = os.path.join(RESULTS_DIR, "router_eval.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
