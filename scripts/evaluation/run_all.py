"""
Master Evaluation Runner — runs all evaluation scripts and prints a
consolidated report.

Usage:
    python scripts/evaluation/run_all.py           # all scripts
    python scripts/evaluation/run_all.py --quick   # skip latency + generation (slow)
    python scripts/evaluation/run_all.py router retrieval  # named scripts only

Outputs: results/eval_summary.json  (aggregated from all per-script JSON files)
"""

import os, sys, json, time, argparse, subprocess
from pathlib import Path

EVAL_DIR    = Path(__file__).parent
RESULTS_DIR = EVAL_DIR / "results"

SCRIPTS = {
    "router":     EVAL_DIR / "router_eval.py",
    "retrieval":  EVAL_DIR / "retrieval_eval.py",
    "generation": EVAL_DIR / "generation_eval.py",
    "latency":    EVAL_DIR / "latency_eval.py",
    "cost":       EVAL_DIR / "cost_eval.py",
    "domain":     EVAL_DIR / "domain_kpis.py",
}

QUICK_SKIP = {"generation", "latency"}  # These are slow; skip in --quick mode


def run_script(name: str, path: Path) -> tuple[bool, float]:
    print(f"\n{'='*60}")
    print(f"  RUNNING: {name.upper()} EVAL  ({path.name})")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(EVAL_DIR.parent.parent),  # project root
    )
    elapsed = time.time() - t0
    ok = result.returncode == 0
    status = "OK" if ok else f"FAILED (exit {result.returncode})"
    print(f"\n  [{status}]  {name} finished in {elapsed:.1f}s")
    return ok, elapsed


def load_results() -> dict:
    """Load all per-script JSON results into one consolidated dict."""
    combined = {}
    result_map = {
        "router":    "router_eval.json",
        "retrieval": "retrieval_eval.json",
        "generation":"generation_eval.json",
        "latency":   "latency_eval.json",
        "cost":      "cost_eval.json",
        "domain":    "domain_kpis.json",
    }
    for key, fname in result_map.items():
        fpath = RESULTS_DIR / fname
        if fpath.exists():
            with open(fpath) as f:
                combined[key] = json.load(f)
        else:
            combined[key] = None
    return combined


def print_consolidated_report(results: dict):
    print("\n" + "=" * 60)
    print("  CONSOLIDATED EVALUATION REPORT")
    print("=" * 60)

    # -- Router ----------------------------------------------------------------
    r = results.get("router")
    if r:
        m8  = r.get("llama3.1-8b",  {})
        m70 = r.get("llama3.1-70b", {})
        print(f"\n  ROUTER ACCURACY")
        print(f"    llama3.1-8b   : {m8.get('overall_accuracy', 0):.1%}  "
              f"({m8.get('correct',0)}/{m8.get('total',0)})")
        print(f"    llama3.1-70b  : {m70.get('overall_accuracy', 0):.1%}  "
              f"({m70.get('correct',0)}/{m70.get('total',0)})")
        delta = r.get("ablation_delta", 0)
        print(f"    Ablation delta: {delta:+.1%}  (70b vs 8b)")

    # -- Retrieval -------------------------------------------------------------
    r = results.get("retrieval")
    if r:
        print(f"\n  RETRIEVAL  (n={r.get('num_queries',0)} queries)")
        print(f"    Precision@1  : {r.get('mean_precision_at_1',0):.3f}")
        print(f"    Precision@3  : {r.get('mean_precision_at_3',0):.3f}")
        print(f"    Precision@8  : {r.get('mean_precision_at_8',0):.3f}")
        print(f"    MRR          : {r.get('mean_mrr',0):.3f}")

    # -- Generation ------------------------------------------------------------
    r = results.get("generation")
    if r:
        print(f"\n  GENERATION QUALITY  (n={r.get('num_queries',0)} queries)")
        print(f"    ROUGE-1 F1   : {r.get('mean_rouge1_f') or 'N/A'}")
        print(f"    ROUGE-2 F1   : {r.get('mean_rouge2_f') or 'N/A'}")
        print(f"    ROUGE-L F1   : {r.get('mean_rougeL_f') or 'N/A'}")
        print(f"    BERTScore F1 : {r.get('mean_bertscore_f1') or 'N/A'}")
        print(f"    Faithfulness : {r.get('mean_faithfulness') or 'N/A'} / 5")
        print(f"    Relevance    : {r.get('mean_relevance') or 'N/A'} / 5")
        print(f"    Groundedness : {r.get('mean_groundedness') or 'N/A'} / 5")

    # -- Latency ---------------------------------------------------------------
    r = results.get("latency")
    if r:
        print(f"\n  LATENCY  ({r.get('total_queries',0)} total queries)")
        print(f"    Overall mean : {r.get('overall_mean_s',0):.2f}s")
        print(f"    Overall p95  : {r.get('overall_p95_s',0):.2f}s")
        pa = r.get("per_agent", {})
        if pa:
            print(f"    {'Agent':<12}  mean    p95")
            for agent, v in pa.items():
                print(f"    {agent:<12}  {v['mean_s']:.2f}s  {v['p95_s']:.2f}s")

    # -- Cost ------------------------------------------------------------------
    r = results.get("cost")
    if r:
        print(f"\n  COST ESTIMATES")
        print(f"    Total (1 query each) : ${r.get('total_cost_usd',0):.6f}")
        print(f"    Avg per query        : ${r.get('avg_cost_per_query',0):.6f}")
        print(f"    Projected per 1k     : ${r.get('projected_per_1k',0):.4f}")

    # -- Domain KPIs -----------------------------------------------------------
    r = results.get("domain")
    if r:
        cov = r.get("coverage_stats", {})
        tc  = r.get("threshold_checks", {})
        def fmt(v):
            try: return f"{int(v):,}"
            except (TypeError, ValueError): return str(v)
        print(f"\n  DOMAIN KPIs  ({tc.get('score','?')} checks passed)")
        print(f"    Episodes indexed    : {fmt(cov.get('curated_episodes', 'N/A'))}")
        print(f"    Chunks indexed      : {fmt(cov.get('curated_chunks', 'N/A'))}")
        print(f"    Claims extracted    : {fmt(cov.get('sem_claims', 'N/A'))}")
        print(f"    Evolution pairs     : {fmt(cov.get('sem_claim_evolution', 'N/A'))}")
        for chk in tc.get("checks", []):
            mark = "PASS" if chk["passed"] else "FAIL"
            print(f"    [{mark}] {chk['check']}")

    print("\n" + "=" * 60)


def main():
    RESULTS_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="Run PodcastIQ evaluation suite")
    parser.add_argument("scripts", nargs="*",
                        help=f"Which evals to run: {list(SCRIPTS.keys())} (default: all)")
    parser.add_argument("--quick", action="store_true",
                        help=f"Skip slow scripts: {QUICK_SKIP}")
    args = parser.parse_args()

    # Determine which scripts to run
    if args.scripts:
        to_run = {k: v for k, v in SCRIPTS.items() if k in args.scripts}
        unknown = set(args.scripts) - set(SCRIPTS.keys())
        if unknown:
            print(f"Unknown eval(s): {unknown}")
            sys.exit(1)
    elif args.quick:
        to_run = {k: v for k, v in SCRIPTS.items() if k not in QUICK_SKIP}
    else:
        to_run = SCRIPTS

    print(f"Running {len(to_run)} evaluation script(s): {list(to_run.keys())}")
    t_start = time.time()

    run_log = []
    for name, path in to_run.items():
        ok, elapsed = run_script(name, path)
        run_log.append({"name": name, "success": ok, "elapsed_s": round(elapsed, 1)})

    total_elapsed = time.time() - t_start
    print(f"\nAll evals done in {total_elapsed:.1f}s")

    # Load + consolidate results
    results = load_results()
    print_consolidated_report(results)

    # Save summary
    summary = {
        "run_log":   run_log,
        "total_elapsed_s": round(total_elapsed, 1),
        "results":   results,
    }
    out_path = RESULTS_DIR / "eval_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Consolidated report saved -> {out_path}")


if __name__ == "__main__":
    main()
