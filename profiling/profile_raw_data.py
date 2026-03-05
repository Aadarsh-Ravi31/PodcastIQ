"""
PodcastIQ — Raw Data Profiling Report
Scans all extracted episodes in data/raw/ and generates a quality profile report.

Usage:
    python profiling/profile_raw_data.py
"""

import json
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
RAW_DATA_DIR = Path("data/raw")
REPORT_DIR = Path("reports")

ARTIFACT_PATTERNS = re.compile(
    r'\[Music\]|\[Applause\]|\[Laughter\]|\[Cheering\]|\[Silence\]|\[Inaudible\]',
    re.IGNORECASE
)

CHANNEL_GENRE_MAP = {
    "lex_fridman_podcast":           "Technology & AI",
    "all-in_podcast":                "Technology & AI",
    "all_in_podcast":                "Technology & AI",
    "no_priors":                     "Technology & AI",
    "acquired_podcast":              "Technology & AI",
    "a16z_podcast":                  "Technology & AI",
    "hard_fork__nyt":                "Technology & AI",
    "the_cognitive_revolution":      "Technology & AI",
    "the_tim_ferriss_show":          "Business & Entrepreneurship",
    "my_first_million":              "Business & Entrepreneurship",
    "lenny_s_podcast":               "Business & Entrepreneurship",
    "wondery__how_i_built_this":     "Business & Entrepreneurship",
    "y_combinator":                  "Business & Entrepreneurship",
    "the_knowledge_project":         "Business & Entrepreneurship",
    "huberman_lab":                  "Science & Health",
    "the_peter_attia_drive":         "Science & Health",
    "foundmyfitness":                "Science & Health",
    "startalk":                      "Science & Health",
    "impact_theory":                 "Education & Self-Improvement",
    "deep_dive_with_ali_abdaal":     "Education & Self-Improvement",
    "the_diary_of_a_ceo":            "Education & Self-Improvement",
    "founders_podcast":              "Education & Self-Improvement",
    "modern_wisdom":                 "Education & Self-Improvement",
    "20vc_with_harry_stebbings":     "Startup & VC",
    "masters_of_scale":              "Startup & VC",
    "joe_rogan_experience":          "Cross-Disciplinary",
}


def get_genre(channel_folder: str) -> str:
    key = channel_folder.lower().replace(" ", "_").replace("-", "_")
    if key in CHANNEL_GENRE_MAP:
        return CHANNEL_GENRE_MAP[key]
    for k, v in CHANNEL_GENRE_MAP.items():
        if k in key or key in k:
            return v
    return "Unknown"


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────
@dataclass
class EpisodeProfile:
    video_id: str
    title: str
    channel_name: str
    genre: str
    segment_count: int
    total_words: int
    duration_minutes: float
    duration_covered: float
    coverage_pct: float
    artifact_count: int
    empty_segments: int
    has_timestamp_gaps: bool
    words_per_minute: float
    avg_segment_duration: float
    quality_score: float


def calculate_quality_score(
    coverage_pct: float,
    artifact_ratio: float,
    wpm: float,
    has_gaps: bool,
    empty_ratio: float
) -> float:
    """Composite quality score 0.0 – 1.0."""
    score = 0.0

    # Coverage (40% weight) — ideal is 0.85-1.05
    if 0.85 <= coverage_pct <= 1.05:
        score += 0.40
    elif 0.50 <= coverage_pct < 0.85:
        score += 0.40 * (coverage_pct / 0.85)
    elif coverage_pct > 1.05:
        score += 0.35  # slight over-coverage is fine
    else:
        score += 0.40 * max(coverage_pct / 0.85, 0)

    # Artifact ratio (20% weight) — lower is better
    score += 0.20 * max(1.0 - artifact_ratio * 10, 0)

    # Words per minute (20% weight) — typical spoken is 120-180 WPM
    if 100 <= wpm <= 200:
        score += 0.20
    elif 50 <= wpm < 100:
        score += 0.10
    elif wpm > 200:
        score += 0.15
    else:
        score += 0.05

    # No timestamp gaps (10% weight)
    score += 0.10 if not has_gaps else 0.0

    # Empty segment ratio (10% weight)
    score += 0.10 * max(1.0 - empty_ratio * 20, 0)

    return round(min(score, 1.0), 3)


def profile_episode(meta_file: Path, channel_name: str, genre: str) -> EpisodeProfile | None:
    """Profile a single episode from its metadata + transcript files."""
    video_id = meta_file.stem.replace("_metadata", "")
    transcript_file = meta_file.parent / f"{video_id}_transcript.json"

    try:
        metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not transcript_file.exists():
        return None

    try:
        segments = json.loads(transcript_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(segments, list) or len(segments) == 0:
        return None

    segment_count = len(segments)
    total_words = sum(len(seg.get("text", "").split()) for seg in segments)
    duration_minutes = metadata.get("duration_minutes", 0)
    duration_seconds = duration_minutes * 60

    # Duration covered by transcript
    last = segments[-1]
    duration_covered = last.get("start", 0) + last.get("duration", 0)

    coverage_pct = duration_covered / duration_seconds if duration_seconds > 0 else 0.0

    # Artifacts
    artifact_count = sum(
        1 for seg in segments if ARTIFACT_PATTERNS.search(seg.get("text", ""))
    )

    # Empty segments
    empty_segments = sum(1 for seg in segments if not seg.get("text", "").strip())

    # Timestamp gaps (>30s)
    has_gaps = False
    for i in range(1, len(segments)):
        prev_end = segments[i-1].get("start", 0) + segments[i-1].get("duration", 0)
        gap = segments[i].get("start", 0) - prev_end
        if gap > 30:
            has_gaps = True
            break

    # Words per minute
    wpm = total_words / duration_minutes if duration_minutes > 0 else 0.0

    # Average segment duration
    avg_seg_dur = sum(seg.get("duration", 0) for seg in segments) / segment_count

    # Quality score
    quality = calculate_quality_score(
        coverage_pct,
        artifact_count / max(segment_count, 1),
        wpm,
        has_gaps,
        empty_segments / max(segment_count, 1)
    )

    return EpisodeProfile(
        video_id=video_id,
        title=metadata.get("title", "Unknown"),
        channel_name=channel_name,
        genre=genre,
        segment_count=segment_count,
        total_words=total_words,
        duration_minutes=duration_minutes,
        duration_covered=duration_covered,
        coverage_pct=coverage_pct,
        artifact_count=artifact_count,
        empty_segments=empty_segments,
        has_timestamp_gaps=has_gaps,
        words_per_minute=wpm,
        avg_segment_duration=avg_seg_dur,
        quality_score=quality,
    )


# ─────────────────────────────────────────────
# Bar chart helper
# ─────────────────────────────────────────────
def bar(count: int, total: int, width: int = 30) -> str:
    filled = int(count / max(total, 1) * width)
    return "\u2588" * filled


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    if not RAW_DATA_DIR.exists():
        print(f"ERROR: {RAW_DATA_DIR} not found. Run extraction first.")
        sys.exit(1)

    profiles: list[EpisodeProfile] = []
    failed_extractions = 0
    channels_seen: set[str] = set()
    genres_seen: set[str] = set()
    channel_episode_counts: dict[str, int] = defaultdict(int)

    # Count total metadata files (= total attempted extractions)
    total_meta_files = 0

    for channel_dir in sorted(RAW_DATA_DIR.iterdir()):
        if not channel_dir.is_dir():
            continue

        channel_name = channel_dir.name
        genre = get_genre(channel_name)
        meta_files = sorted(channel_dir.glob("*_metadata.json"))

        if not meta_files:
            continue

        channels_seen.add(channel_name)
        genres_seen.add(genre)
        total_meta_files += len(meta_files)

        for mf in meta_files:
            ep = profile_episode(mf, channel_name, genre)
            if ep:
                profiles.append(ep)
                channel_episode_counts[channel_name] += 1
            else:
                failed_extractions += 1

    # ── Compute aggregate stats ────────────────────────
    total_extracted = total_meta_files
    successful = len(profiles)
    failed = failed_extractions
    fail_pct = failed / max(total_extracted, 1) * 100

    # Quality buckets
    high   = [p for p in profiles if p.quality_score > 0.7]
    medium = [p for p in profiles if 0.5 <= p.quality_score <= 0.7]
    low    = [p for p in profiles if p.quality_score < 0.5]

    # Accepted = quality >= 0.5 (HIGH + MEDIUM)
    accepted = len(high) + len(medium)
    rejected = len(low)

    # Segment stats
    total_segments = sum(p.segment_count for p in profiles)
    avg_segments = total_segments / max(successful, 1)

    # Word stats
    total_words = sum(p.total_words for p in profiles)
    avg_words = total_words / max(successful, 1)

    # Artifact rate
    total_artifacts = sum(p.artifact_count for p in profiles)
    artifact_rate = total_artifacts / max(total_segments, 1) * 100

    # Empty segment rate
    total_empty = sum(p.empty_segments for p in profiles)
    empty_rate = total_empty / max(total_segments, 1) * 100

    # Timestamp gap rate
    gap_episodes = sum(1 for p in profiles if p.has_timestamp_gaps)
    gap_rate = gap_episodes / max(successful, 1) * 100

    # WPM stats
    avg_wpm = sum(p.words_per_minute for p in profiles) / max(successful, 1)
    min_wpm = min((p.words_per_minute for p in profiles), default=0)
    max_wpm = max((p.words_per_minute for p in profiles), default=0)

    # Duration stats
    total_hours = sum(p.duration_minutes for p in profiles) / 60
    avg_duration = sum(p.duration_minutes for p in profiles) / max(successful, 1)

    # Coverage stats
    avg_coverage = sum(p.coverage_pct for p in profiles) / max(successful, 1) * 100

    # Genre distribution
    genre_counts: dict[str, int] = defaultdict(int)
    for p in profiles:
        genre_counts[p.genre] += 1

    # Channel stats
    total_channels_config = 25  # from channels.json
    channels_with_data = len(channels_seen)
    total_genres_config = len(set(CHANNEL_GENRE_MAP.values()))

    # ── Build report ───────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    W = 60

    lines = []
    sep = "\u2550" * W

    lines.append("")
    lines.append(sep)
    lines.append("  PodcastIQ Extraction Profile Report")
    lines.append(f"  Date: {now}")
    lines.append(sep)
    lines.append("")
    lines.append("  EXTRACTION SUMMARY")
    lines.append("  " + "-" * 40)
    lines.append(f"  Total videos extracted:     {total_extracted:>5}")
    lines.append(f"  Successful transcripts:     {successful:>5}")
    lines.append(f"  Failed extractions:         {failed:>5} ({fail_pct:.1f}%)")
    lines.append("")
    lines.append("  QUALITY DISTRIBUTION")
    lines.append("  " + "-" * 40)
    lines.append(f"  {bar(len(high), successful)} HIGH (>0.7):    {len(high):>5} ({len(high)/max(successful,1)*100:.1f}%)")
    lines.append(f"  {bar(len(medium), successful)} MEDIUM (0.5-0.7): {len(medium):>3} ({len(medium)/max(successful,1)*100:.1f}%)")
    lines.append(f"  {bar(len(low), successful)} LOW (<0.5):       {len(low):>3} ({len(low)/max(successful,1)*100:.1f}%)")
    lines.append("")
    lines.append(f"  Accepted for loading:       {accepted:>5}")
    lines.append(f"  Rejected:                   {rejected:>5}")
    lines.append("")
    lines.append("  TRANSCRIPT METRICS")
    lines.append("  " + "-" * 40)
    lines.append(f"  Avg segments per episode:   {avg_segments:>7,.0f}")
    lines.append(f"  Avg words per episode:      {avg_words:>7,.0f}")
    lines.append(f"  Total segments:             {total_segments:>7,}")
    lines.append(f"  Total words in dataset:     {total_words:>10,}")
    lines.append(f"  Avg coverage (transcript/video): {avg_coverage:>5.1f}%")
    lines.append("")
    lines.append("  WORDS PER MINUTE")
    lines.append("  " + "-" * 40)
    lines.append(f"  Average WPM:                {avg_wpm:>7.1f}")
    lines.append(f"  Min WPM:                    {min_wpm:>7.1f}")
    lines.append(f"  Max WPM:                    {max_wpm:>7.1f}")
    lines.append("")
    lines.append("  DURATION")
    lines.append("  " + "-" * 40)
    lines.append(f"  Total hours of content:     {total_hours:>7.1f} hrs")
    lines.append(f"  Avg episode duration:       {avg_duration:>7.1f} min")
    lines.append("")
    lines.append("  DATA QUALITY FLAGS")
    lines.append("  " + "-" * 40)
    lines.append(f"  Artifact rate:              {artifact_rate:>5.1f}% of segments")
    lines.append(f"  Empty segment rate:         {empty_rate:>5.1f}% of segments")
    lines.append(f"  Timestamp gap rate:         {gap_rate:>5.1f}% of episodes")
    lines.append("")
    lines.append("  COVERAGE")
    lines.append("  " + "-" * 40)
    lines.append(f"  Channel Coverage:           {channels_with_data}/{total_channels_config}")
    lines.append(f"  Genre Coverage:             {len(genres_seen)}/{total_genres_config}")
    lines.append("")
    lines.append("  GENRE BREAKDOWN")
    lines.append("  " + "-" * 40)
    for genre, count in sorted(genre_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {bar(count, successful, 20)} {genre}: {count}")
    lines.append("")
    lines.append("  CHANNEL BREAKDOWN (episodes per channel)")
    lines.append("  " + "-" * 40)
    for ch, count in sorted(channel_episode_counts.items(), key=lambda x: -x[1]):
        lines.append(f"    {count:>3}  {ch}")

    # Bottom 5 quality episodes
    lines.append("")
    lines.append("  LOWEST QUALITY EPISODES (bottom 5)")
    lines.append("  " + "-" * 40)
    bottom5 = sorted(profiles, key=lambda p: p.quality_score)[:5]
    for ep in bottom5:
        lines.append(f"    {ep.quality_score:.3f}  {ep.channel_name}/{ep.video_id}")
        lines.append(f"           {ep.title[:55]}...")

    # Per-video quality scores (all episodes)
    lines.append("")
    lines.append("  ALL EPISODES — QUALITY SCORES")
    lines.append("  " + "-" * 80)
    lines.append(f"  {'Score':<8}{'Coverage':<10}{'WPM':<8}{'Segments':<10}{'Words':<10}{'Channel':<30}{'Title'}")
    lines.append("  " + "-" * 80)
    for ep in sorted(profiles, key=lambda p: (-p.quality_score, p.channel_name)):
        lines.append(
            f"  {ep.quality_score:<8.3f}"
            f"{ep.coverage_pct*100:<10.1f}"
            f"{ep.words_per_minute:<8.0f}"
            f"{ep.segment_count:<10,}"
            f"{ep.total_words:<10,}"
            f"{ep.channel_name:<30}"
            f"{ep.title[:50]}"
        )

    lines.append("")
    lines.append(sep)
    lines.append("")

    report = "\n".join(lines)
    print(report)

    # Save report
    REPORT_DIR.mkdir(exist_ok=True)
    report_path = REPORT_DIR / "extraction_profile_report.txt"
    report_path.write_text(report, encoding="utf-8")
    print(f"  Report saved to: {report_path}")


if __name__ == "__main__":
    main()
