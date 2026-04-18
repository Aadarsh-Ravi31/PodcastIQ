"""
Domain KPIs -- measures corpus health and pipeline quality via SQL.

Checks:
1. Coverage Stats      -- chunks, claims, evolution pairs, participants
2. Pipeline Completeness -- % claims with speaker, drift type distribution
3. Claim Evolution Validity -- spot-check that ORIGINAL/EVOLVED claim IDs differ
4. YouTube URL Validity -- spot-check that stored URLs follow expected pattern
5. Speaker Attribution  -- % claims with non-null speaker attribution

Outputs: results/domain_kpis.json
"""

import os, sys, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.snowflake_client import execute, execute_scalar

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# -- YouTube URL pattern -------------------------------------------------------
YOUTUBE_URL_RE = re.compile(
    r'^https://(?:www\.)?youtube\.com/watch\?v=[\w-]{11}'
    r'(?:&t=\d+s?)?$'
)


def safe_int(val) -> int:
    try:
        return int(val or 0)
    except (TypeError, ValueError):
        return 0


def safe_print(s: str):
    """Print string, replacing unencodable chars with '?'."""
    print(s.encode("cp1252", errors="replace").decode("cp1252"))


def check_coverage_stats() -> dict:
    safe_print("\n-- Coverage Stats --")
    queries = {
        "curated_chunks":       "SELECT COUNT(*) FROM PODCASTIQ.CURATED.CUR_CHUNKS",
        "sem_claims":           "SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CLAIMS",
        "sem_claim_evolution":  "SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CLAIM_EVOLUTION",
        "sem_participants":     "SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_EPISODE_PARTICIPANTS",
        "sem_embeddings":       "SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CHUNK_EMBEDDINGS",
        "unique_channels":      "SELECT COUNT(DISTINCT CHANNEL_NAME) FROM PODCASTIQ.CURATED.CUR_CHUNKS",
        "unique_speakers":      "SELECT COUNT(DISTINCT SPEAKER) FROM PODCASTIQ.SEMANTIC.SEM_CLAIMS WHERE SPEAKER IS NOT NULL",
        "unique_episodes":      "SELECT COUNT(DISTINCT VIDEO_ID) FROM PODCASTIQ.CURATED.CUR_CHUNKS",
    }
    stats = {}
    for key, sql in queries.items():
        try:
            val = safe_int(execute_scalar(sql))
            stats[key] = val
            safe_print(f"  {key:<30s}: {val:>8,}")
        except Exception as e:
            stats[key] = f"ERROR: {e}"
            safe_print(f"  {key:<30s}: ERROR - {e}")
    return stats


def check_pipeline_completeness() -> dict:
    safe_print("\n-- Pipeline Completeness --")
    results = {}

    # % claims with non-null speaker
    try:
        total_claims = safe_int(execute_scalar("SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CLAIMS"))
        claims_w_spk = safe_int(execute_scalar("""
            SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CLAIMS
            WHERE SPEAKER IS NOT NULL AND SPEAKER != ''
        """))
        pct = round(claims_w_spk / total_claims * 100, 1) if total_claims else 0
        results["claims_with_speaker_pct"] = pct
        safe_print(f"  Claims with speaker       : {claims_w_spk}/{total_claims}  ({pct}%)")
    except Exception as e:
        results["claims_with_speaker_pct"] = f"ERROR: {e}"
        safe_print(f"  Claims with speaker       : ERROR - {e}")

    # % chunks with embeddings
    try:
        total_chunks = safe_int(execute_scalar("SELECT COUNT(*) FROM PODCASTIQ.CURATED.CUR_CHUNKS"))
        chunks_w_emb = safe_int(execute_scalar("SELECT COUNT(*) FROM PODCASTIQ.SEMANTIC.SEM_CHUNK_EMBEDDINGS"))
        pct = round(chunks_w_emb / total_chunks * 100, 1) if total_chunks else 0
        results["chunks_with_embeddings_pct"] = pct
        safe_print(f"  Chunks with embeddings    : {chunks_w_emb}/{total_chunks}  ({pct}%)")
    except Exception as e:
        results["chunks_with_embeddings_pct"] = f"ERROR: {e}"
        safe_print(f"  Chunks with embeddings    : ERROR - {e}")

    # Drift type distribution (SEM_CLAIM_EVOLUTION uses DRIFT_TYPE)
    try:
        rows = execute("""
            SELECT DRIFT_TYPE, COUNT(*) AS CNT
            FROM PODCASTIQ.SEMANTIC.SEM_CLAIM_EVOLUTION
            GROUP BY DRIFT_TYPE
            ORDER BY CNT DESC
        """)
        dist = {r.get("DRIFT_TYPE", "?"): safe_int(r.get("CNT")) for r in rows}
        results["drift_type_distribution"] = dist
        safe_print(f"  Drift type distribution   : {dist}")
    except Exception as e:
        results["drift_type_distribution"] = f"ERROR: {e}"
        safe_print(f"  Drift type distribution   : ERROR - {e}")

    return results


def check_claim_evolution_validity(sample_size: int = 20) -> dict:
    """Spot-check that ORIGINAL_CLAIM_ID and EVOLVED_CLAIM_ID are different."""
    safe_print("\n-- Claim Evolution Validity --")
    try:
        rows = execute(f"""
            SELECT
                EVOLUTION_ID,
                ORIGINAL_CLAIM_ID,
                EVOLVED_CLAIM_ID,
                DRIFT_TYPE,
                ANALYSIS
            FROM PODCASTIQ.SEMANTIC.SEM_CLAIM_EVOLUTION
            LIMIT {sample_size}
        """)
    except Exception as e:
        safe_print(f"  ERROR: {e}")
        return {"error": str(e)}

    if not rows:
        safe_print("  No evolution pairs found.")
        return {"sampled": 0, "identical_pairs": 0, "identity_rate_pct": None}

    identical = 0
    has_analysis = 0
    for row in rows:
        orig = (row.get("ORIGINAL_CLAIM_ID") or "").strip()
        evol = (row.get("EVOLVED_CLAIM_ID")  or "").strip()
        if orig == evol:
            identical += 1
        if row.get("ANALYSIS"):
            has_analysis += 1

    identity_rate = round(identical / len(rows) * 100, 1)
    valid_rate    = 100 - identity_rate
    analysis_pct  = round(has_analysis / len(rows) * 100, 1)
    safe_print(f"  Sample size               : {len(rows)}")
    safe_print(f"  Identical IDs (bad)       : {identical}  ({identity_rate}%)")
    safe_print(f"  Valid pairs (differ)      : {len(rows)-identical}  ({valid_rate}%)")
    safe_print(f"  Pairs with analysis text  : {has_analysis}  ({analysis_pct}%)")

    return {
        "sampled":            len(rows),
        "identical_pairs":    identical,
        "identity_rate_pct":  identity_rate,
        "valid_rate_pct":     valid_rate,
        "analysis_coverage":  analysis_pct,
    }


def check_youtube_url_validity(sample_size: int = 50) -> dict:
    """Spot-check that stored YouTube URLs match expected pattern."""
    safe_print("\n-- YouTube URL Validity --")
    try:
        rows = execute(f"""
            SELECT DISTINCT YOUTUBE_URL
            FROM PODCASTIQ.CURATED.CUR_CHUNKS
            WHERE YOUTUBE_URL IS NOT NULL
            LIMIT {sample_size}
        """)
    except Exception as e:
        safe_print(f"  ERROR: {e}")
        return {"error": str(e)}

    if not rows:
        safe_print("  No YouTube URLs found to validate.")
        return {"sampled": 0}

    valid   = 0
    invalid = 0
    malformed_examples = []

    for row in rows:
        url = str(row.get("YOUTUBE_URL") or "").strip()
        if YOUTUBE_URL_RE.match(url):
            valid += 1
        else:
            invalid += 1
            if len(malformed_examples) < 5:
                malformed_examples.append(url)

    total     = valid + invalid
    valid_pct = round(valid / total * 100, 1) if total else 0
    safe_print(f"  Sample size               : {total}")
    safe_print(f"  Valid URLs                : {valid}  ({valid_pct}%)")
    safe_print(f"  Invalid/malformed URLs    : {invalid}")
    if malformed_examples:
        safe_print(f"  Examples of bad URLs      : {malformed_examples[:3]}")

    return {
        "sampled":            total,
        "valid_urls":         valid,
        "invalid_urls":       invalid,
        "valid_pct":          valid_pct,
        "malformed_examples": malformed_examples,
    }


def check_temporal_freshness() -> dict:
    """Check date range of corpus via CUR_CHUNKS."""
    safe_print("\n-- Temporal Freshness --")
    results = {}
    try:
        row = execute("""
            SELECT
                MIN(PUBLISH_DATE) AS OLDEST,
                MAX(PUBLISH_DATE) AS NEWEST,
                COUNT(DISTINCT DATE_TRUNC('month', PUBLISH_DATE)) AS MONTHS_COVERED
            FROM PODCASTIQ.CURATED.CUR_CHUNKS
            WHERE PUBLISH_DATE IS NOT NULL
        """)
        if row:
            r = row[0]
            oldest = str(r.get("OLDEST",  "?"))
            newest = str(r.get("NEWEST",  "?"))
            months = safe_int(r.get("MONTHS_COVERED", 0))
            results = {"oldest_episode": oldest, "newest_episode": newest, "months_covered": months}
            safe_print(f"  Oldest episode            : {oldest}")
            safe_print(f"  Newest episode            : {newest}")
            safe_print(f"  Months covered            : {months}")
    except Exception as e:
        results = {"error": str(e)}
        safe_print(f"  ERROR: {e}")
    return results


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)
    print("=" * 60)
    print("DOMAIN KPIs")
    print("=" * 60)

    report = {}

    report["coverage_stats"]            = check_coverage_stats()
    report["pipeline_completeness"]     = check_pipeline_completeness()
    report["claim_evolution_validity"]  = check_claim_evolution_validity()
    report["youtube_url_validity"]      = check_youtube_url_validity()
    report["temporal_freshness"]        = check_temporal_freshness()

    # -- Pass / Fail thresholds ------------------------------------------------
    print("\n-- Pass / Fail Assessment --")
    cov = report["coverage_stats"]
    pc  = report["pipeline_completeness"]
    ev  = report["claim_evolution_validity"]
    url = report["youtube_url_validity"]

    checks = [
        ("chunks indexed >= 6000",
            safe_int(cov.get("curated_chunks", 0)) >= 6000),
        ("claims extracted >= 1000",
            safe_int(cov.get("sem_claims", 0)) >= 1000),
        ("evolution pairs >= 100",
            safe_int(cov.get("sem_claim_evolution", 0)) >= 100),
        ("claims with speaker >= 50%",
            (pc.get("claims_with_speaker_pct") or 0) >= 50),
        ("chunks with embeddings >= 90%",
            (pc.get("chunks_with_embeddings_pct") or 0) >= 90),
        ("evolution pairs valid >= 90%",
            (ev.get("valid_rate_pct") or 0) >= 90),
        ("YouTube URLs valid >= 95%",
            (url.get("valid_pct") or 0) >= 95),
    ]

    passed = 0
    check_results = []
    for desc, ok in checks:
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        print(f"  [{status}]  {desc}")
        check_results.append({"check": desc, "passed": ok})

    report["threshold_checks"] = {
        "passed": passed,
        "total":  len(checks),
        "score":  f"{passed}/{len(checks)}",
        "checks": check_results,
    }

    print("\n" + "=" * 60)
    print(f"  Domain KPIs Score: {passed}/{len(checks)} checks passed")

    out_path = os.path.join(RESULTS_DIR, "domain_kpis.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nSaved -> {out_path}")


if __name__ == "__main__":
    main()
