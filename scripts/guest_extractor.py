"""
PodcastIQ — guest_extractor.py
Two-Tier Speaker Attribution: extracts host and guest names from episode metadata.

Tier 1 (TITLE_PARSE): Channel-specific regex patterns against episode title.
  Covers ~80% of episodes with zero LLM calls.

Tier 2 (LLM_INFERRED): Snowflake Cortex COMPLETE fallback for unmatched titles.
  Only fires when regex produces no guest name.

Output: INSERT into SEMANTIC.SEM_EPISODE_PARTICIPANTS
"""

import json
import logging
import os
import re
from dataclasses import dataclass

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Channel configuration
# ─────────────────────────────────────────────

@dataclass
class ChannelConfig:
    hosts: list[str]                 # Known permanent hosts
    guest_patterns: list[str]        # Ordered list of regex patterns to try (first match wins)
    solo_show: bool = False          # True = no guest expected (skip LLM fallback)


# Each pattern must have exactly one capture group: the guest name (or comma-separated names)
CHANNEL_CONFIG: dict[str, ChannelConfig] = {

    "20VC with Harry Stebbings": ChannelConfig(
        hosts=["Harry Stebbings"],
        guest_patterns=[
            # "Role, First Last: subtitle"  e.g. "Groq Founder, Jonathan Ross: ..."
            r",\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "Role First Last: subtitle" no comma  e.g. "Klarna CEO Siemiatkowski: ..."
            r"(?:CEO|Founder|Partner|Head|GP|CTO|COO|President)\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
        ],
    ),

    "Acquired": ChannelConfig(
        hosts=["Ben Gilbert", "David Rosenthal"],
        guest_patterns=[
            # "(with Doug DeMuro)"
            r"\(with\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\)",
            # "NVIDIA CEO Jensen Huang" or "TSMC founder Morris Chang"
            r"(?:CEO|founder|Co-Founder|Chairman)\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "The Mark Zuckerberg Interview"
            r"^The\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+Interview",
            # "Charlie Munger (Audio)" — title IS the person
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*(?:\(Audio\))?$",
        ],
    ),

    "Ali Abdaal": ChannelConfig(
        hosts=["Ali Abdaal"],
        guest_patterns=[],
        solo_show=True,
    ),

    "All-In Podcast": ChannelConfig(
        hosts=["Chamath Palihapitiya", "Jason Calacanis", "David Sacks", "David Friedberg"],
        guest_patterns=[
            # "In conversation with X"
            r"[Ii]n conversation with (.+?)(?:\s*\|.*)?$",
            # "Tucker Carlson: State of America..." — named guest as subject
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-.]+)?):",
            # "John Mearsheimer vs. Jeffrey Sachs"
            r"([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+vs\.?\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),

    "Andrew Huberman": ChannelConfig(
        hosts=["Andrew Huberman"],
        guest_patterns=[
            # "Topic | Guest Name" — person after last pipe (skip "Huberman Lab Essentials")
            r"\|\s*((?:Dr\.\s+)?[A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-\.]+)+)\s*$",
            # "Dr. Andy Galpin: subtitle" — Dr. at start
            r"^(Dr\.\s+[A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
        ],
        # Filter out "Huberman Lab Essentials" matches (solo episodes)
    ),

    "Chris Williamson": ChannelConfig(
        hosts=["Chris Williamson"],
        guest_patterns=[
            # "Topic - Guest Name" or "Topic - Guest Name (4K)"
            r"\s+-\s+((?:Dr\.?\s+)?[A-Z][a-zA-Z\-]+(?:\s+[a-zA-Z\-]+)*)\s*(?:\(\d+K\))?$",
        ],
    ),

    'Cognitive Revolution "How AI Changes Everything"': ChannelConfig(
        hosts=["Nathan Labenz", "Erik Torenberg"],
        guest_patterns=[
            # "w/ Name" or "w- Name"
            r"\bw[/\-]\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "with CEO/Founder Name" or "with Name of Company"
            r"\bwith\s+(?:\w+\s+){0,3}([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),

    "FoundMyFitness": ChannelConfig(
        hosts=["Rhonda Patrick"],
        guest_patterns=[
            # "Dr. Ben Bikman: subtitle"
            r"^(Dr\.\s+[A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "Andrew Huberman, PhD: subtitle"
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+),\s*(?:PhD|MD|DO)\s*:",
            # "Stuart Phillips, PhD, on Building..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+),\s*(?:PhD|MD|DO),\s*on\b",
            # "Topic | Dr. Rhonda Patrick" — own host appearing as guest elsewhere
            r"\|\s*((?:Dr\.\s+)?[A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
        ],
    ),

    "Founders Podcast": ChannelConfig(
        hosts=["David Senra"],
        guest_patterns=[
            # "How Bill Gates Works" → Bill Gates
            r"^(?:How|The Story of|Lessons from)\s+([A-Z][a-zA-Z\-]+(?:'s)?\s+[A-Z][a-zA-Z\-]+)",
            # "Li Lu and Charlie Munger and Warren Buffett"
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+and",
        ],
    ),

    "Hard Fork": ChannelConfig(
        hosts=["Kevin Roose", "Casey Newton"],
        guest_patterns=[
            # "Debriefing Dinner with Sam Altman"
            r"\bwith\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)(?:\s*[\.!\|]|$)",
            # "Meet Anthropic Philosopher Amanda Askell"
            r"\bMeet\s+(?:\w+\s+){0,3}([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "Dario Amodei of Anthropic's Hopes..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+(?:of|on|talks)\b",
            # "DeepMind CEO Demis Hassabis on..."
            r"(?:CEO|C\.E\.O\.|Founder)\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+on\b",
        ],
    ),

    "Lenny's Podcast": ChannelConfig(
        hosts=["Lenny Rachitsky"],
        guest_patterns=[
            # "Topic | Guest Name (company)"
            r"\|\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)(?:\s*\([^)]+\))?$",
            # "topic: Bret Taylor (Sierra)" — name before company in parens at end
            r":\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*(?:\([^)]+\))?$",
            # "Marc Andreessen: The real AI boom..." — name at start before colon
            r"^([A-Z][a-zA-Z\-']+\s+[A-Z][a-zA-Z\-']+)\s*:",
        ],
    ),

    "Lex Fridman": ChannelConfig(
        hosts=["Lex Fridman"],
        guest_patterns=[
            # "Jeff Bezos: Amazon... | Lex Fridman Podcast #N"
            r"^([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-\.]+)+)\s*:",
            # "Donald Trump Interview | Lex Fridman..."
            r"^([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-\.]+)+)\s+Interview",
            # "Ben Shapiro vs Destiny Debate..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+vs",
        ],
    ),

    "Masters of Scale": ChannelConfig(
        hosts=["Reid Hoffman"],
        guest_patterns=[
            # "(with founders David Heath & Randy Goldberg)"
            r"\(with\s+(?:\w+\s+){0,3}([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\)",
            # "Cotopaxi's Davis Smith: Lessons..."
            r"^[A-Za-z0-9'\-]+['s]?\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "Danny & Hallie Meyer: Lessons..."
            r"^([A-Z][a-zA-Z\-]+\s+(?:&\s+[A-Z][a-zA-Z\-]+\s+)?[A-Z][a-zA-Z\-]+)\s*:",
            # "with Zola's Shan-Lyn Ma"
            r"\bwith\s+(?:[A-Za-z0-9'\-]+['s]?\s+)?([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),

    "My First Million": ChannelConfig(
        hosts=["Sam Parr", "Shaan Puri"],
        guest_patterns=[
            # "| Sarah Moore Interview"
            r"\|\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+Interview$",
            # "| Tim Ferriss" at end
            r"\|\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
            # "- Scott Galloway" at end
            r"\s+-\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
            # "Confronting Cathie Wood About..."
            r"^Confronting\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+",
        ],
    ),

    "No Priors: AI, Machine Learning, Tech, & Startups": ChannelConfig(
        hosts=["Sarah Guo", "Elad Gil"],
        guest_patterns=[
            # "No Priors Ep. 131 | With Jared Kushner"
            r"\|\s*[Ww]ith\s+(?:(?:[A-Z][a-z]+\s+){0,3})?([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
            # "No Priors Ep. 101 | With Harvey CEO and Co-Founder Winston Weinberg"
            r"\|\s*[Ww]ith\s+.+?([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
            # "Rivian CEO RJ Scaringe"
            r"(?:CEO|Founder|Co-Founder|President)\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),

    "Peter Attia MD": ChannelConfig(
        hosts=["Peter Attia"],
        guest_patterns=[
            # Most are solo; occasional "roundtable" or named guest
            r"\bwith\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),

    "PowerfulJRE": ChannelConfig(
        hosts=["Joe Rogan"],
        guest_patterns=[
            # "Joe Rogan Experience #2422 - Jensen Huang"
            r"#\d+\s+-\s+(.+)$",
        ],
    ),

    "StarTalk": ChannelConfig(
        hosts=["Neil deGrasse Tyson"],
        guest_patterns=[
            # "Do We Have To Die? With Venki Ramakrishnan"
            r"\bWith\s+([A-Z][a-zA-Z\-\.]+(?:\s+[a-zA-Z\-\.]+)*)$",
            # "Breaking Down UAP...with the Head of The Pentagon's UAP Taskforce, Dr. Jon Kosloski"
            r"\bwith\s+.+?,\s+((?:Dr\.\s+)?[A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "Tackling...with 3Blue1Brown"
            r"\bwith\s+([A-Za-z0-9]+(?:[A-Z][a-zA-Z\-]+)?)\s*$",
        ],
    ),

    "The Diary Of A CEO": ChannelConfig(
        hosts=["Steven Bartlett"],
        guest_patterns=[
            # "Jordan Peterson: How To Become..."
            r"^([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-\.]+)+)\s*:",
            # "Ex-Google Exec (WARNING): The Next 15 Years... - Mo Gawdat"
            r"\s+-\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*(?:\|.*)?$",
            # "CIA Spy: ...: Andrew Bustamante" (colon-name at end)
            r":\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
        ],
    ),

    "The Knowledge Project Podcast": ChannelConfig(
        hosts=["Shane Parrish"],
        guest_patterns=[
            # "Dr. Becky Kennedy: ..." or "Morgan Housel: ..."
            r"^((?:Dr\.\s+)?[A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "My conversation with Pierre Poilievre"
            r"conversation with\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "84-Year-Old Billionaire: How I Turned... | John Bragg"
            r"\|\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*$",
        ],
    ),

    "Tim Ferriss": ChannelConfig(
        hosts=["Tim Ferriss"],
        guest_patterns=[
            # "Chris Sacca — How to Succeed..." (em dash)
            r"^([A-Z][a-zA-Z\-]+(?:\s+[A-Z][a-zA-Z\-\.]+)+)\s*[—\u2012\u2013]",
            # "Naval Ravikant and Aaron Stupple — ..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+and\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
            # "Rhonda Patrick, Ph.D. — ..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+),\s*(?:Ph\.D\.|MD|PhD)",
        ],
    ),

    "Tom Bilyeu": ChannelConfig(
        hosts=["Tom Bilyeu"],
        guest_patterns=[],
        solo_show=True,
    ),

    "Wondery": ChannelConfig(
        hosts=["Guy Raz"],
        guest_patterns=[
            r"\bwith\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)(?:\s*\||\s*$)",
        ],
    ),

    "Y Combinator": ChannelConfig(
        hosts=["Garry Tan", "Harj Taggar"],
        guest_patterns=[
            # "Alexandr Wang: Building Scale AI..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "Elon Musk: Digital Superintelligence..." (longer names)
            r"^([A-Z][a-zA-Z\-]+(?:\s+[a-zA-Z\-]+)?\s+[A-Z][a-zA-Z\-]+)\s*:",
        ],
    ),

    "a16z": ChannelConfig(
        hosts=["Marc Andreessen", "Ben Horowitz", "a16z Partners"],
        guest_patterns=[
            # "Sam Altman on Sora..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+on\b",
            # "Mark Zuckerberg & Priscilla Chan: ..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*(?:&|and)\s*([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s*:",
            # "Marc Andreessen's 2026 Outlook..."
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)'s\b",
            # "Dylan Patel on the AI Chip Race"
            r"^([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)\s+on\s+the\b",
            # "with Marc Andreessen"
            r"\bwith\s+([A-Z][a-zA-Z\-]+\s+[A-Z][a-zA-Z\-]+)",
        ],
    ),
}


# ─────────────────────────────────────────────
# Tier 1: regex extraction
# ─────────────────────────────────────────────

def _clean_name(raw: str) -> str:
    """Strip trailing noise like '(a16z)', '| EP 150', role words after name, etc."""
    raw = raw.strip()
    # Remove trailing parenthetical "(company)" or "(Audio)"
    raw = re.sub(r"\s*\([^)]+\)\s*$", "", raw).strip()
    # Remove trailing " | ..." suffixes
    raw = re.sub(r"\s*\|.*$", "", raw).strip()
    # Remove trailing episode markers "| EP 150"
    raw = re.sub(r"\s*\|\s*EP\s*\d+.*$", "", raw, flags=re.IGNORECASE).strip()
    return raw


def extract_guests_from_title(channel: str, title: str) -> list[str]:
    """
    Apply channel-specific regex patterns to episode title.
    Returns list of guest name strings (may be empty).
    """
    config = CHANNEL_CONFIG.get(channel)
    if not config:
        return []

    if config.solo_show:
        return []

    for pattern in config.guest_patterns:
        m = re.search(pattern, title)
        if not m:
            continue

        # Collect all capture groups
        groups = [g for g in m.groups() if g]
        if not groups:
            continue

        names = []
        for raw in groups:
            cleaned = _clean_name(raw)
            if not cleaned:
                continue
            # Skip if it matches a known host (case-insensitive)
            if any(h.lower() in cleaned.lower() for h in config.hosts):
                continue
            # Skip generic terms
            if re.match(r"^(Huberman Lab Essentials|Interview|Podcast|Bonus|Summary)$", cleaned, re.I):
                continue
            if len(cleaned.split()) < 2:
                continue
            names.append(cleaned)

        if names:
            return names

    return []


# ─────────────────────────────────────────────
# Tier 2: LLM fallback (batch via Snowflake)
# ─────────────────────────────────────────────

LLM_FALLBACK_PROMPT = """You are extracting guest names from a podcast episode title.

Channel: {channel}
Episode title: "{title}"

If there is a clearly named guest in the title, respond with ONLY their full name (First Last).
If there are multiple guests, separate with " | ".
If there is no named guest or this is a solo episode, respond with exactly: NONE

Respond with nothing else."""


def _llm_extract_guest(cursor, channel: str, title: str) -> list[str]:
    prompt = LLM_FALLBACK_PROMPT.format(channel=channel, title=title)
    cursor.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (prompt,),
    )
    row = cursor.fetchone()
    if not row:
        return []
    result = (row[0] or "").strip()
    if result.upper() == "NONE" or not result:
        return []
    return [n.strip() for n in result.split("|") if n.strip()]


# ─────────────────────────────────────────────
# Main extraction pipeline
# ─────────────────────────────────────────────

def get_connection():
    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    with open(key_path, "rb") as f:
        pk = serialization.load_pem_private_key(
            f.read(),
            password=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").encode() or None,
            backend=default_backend(),
        )
    pk_bytes = pk.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=pk_bytes,
        warehouse="PODCASTIQ_WH",
        database="PODCASTIQ",
        schema="SEMANTIC",
        role="TRAINING_ROLE",
    )


def run():
    conn = get_connection()
    cur = conn.cursor()

    # Fetch all distinct episodes not yet in SEM_EPISODE_PARTICIPANTS
    log.info("Fetching episodes...")
    cur.execute("""
        SELECT DISTINCT VIDEO_ID, CHANNEL_NAME, EPISODE_TITLE
        FROM CURATED.CUR_CHUNKS
        WHERE VIDEO_ID NOT IN (
            SELECT DISTINCT VIDEO_ID FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        )
        ORDER BY CHANNEL_NAME, EPISODE_TITLE
    """)
    episodes = cur.fetchall()
    log.info(f"Processing {len(episodes)} episodes")

    rows_to_insert = []
    llm_fallback_count = 0
    stats = {"regex_hit": 0, "llm_hit": 0, "no_guest": 0}

    for video_id, channel, title in episodes:
        config = CHANNEL_CONFIG.get(channel)
        hosts = config.hosts if config else []

        # Always insert all known hosts
        for host in hosts:
            rows_to_insert.append((
                video_id, host, "HOST", "MANUAL", "HIGH", channel, title
            ))

        # Tier 1: regex
        guests = extract_guests_from_title(channel, title)

        # Tier 2: LLM fallback (only if channel is not solo and regex found nothing)
        if not guests and config and not config.solo_show and config.guest_patterns:
            guests = _llm_extract_guest(cur, channel, title)
            if guests:
                llm_fallback_count += 1
                method = "LLM_INFERRED"
                confidence = "MEDIUM"
                stats["llm_hit"] += 1
                log.info(f"  LLM fallback -> {guests[0]!r} for: {title[:60]}")
            else:
                stats["no_guest"] += 1
                method = "TITLE_PARSE"
                confidence = "LOW"
        else:
            method = "TITLE_PARSE" if guests else "TITLE_PARSE"
            confidence = "HIGH" if guests else "LOW"
            if guests:
                stats["regex_hit"] += 1
            else:
                stats["no_guest"] += 1

        for guest in guests:
            rows_to_insert.append((
                video_id, guest, "GUEST", method, confidence, channel, title
            ))

    log.info(
        f"\nExtraction stats:\n"
        f"  Regex matched : {stats['regex_hit']}\n"
        f"  LLM fallback  : {stats['llm_hit']}\n"
        f"  No guest found: {stats['no_guest']}\n"
        f"  Total rows    : {len(rows_to_insert)}"
    )

    # Batch INSERT
    if rows_to_insert:
        log.info(f"Inserting {len(rows_to_insert)} rows into SEM_EPISODE_PARTICIPANTS...")
        cur.executemany("""
            INSERT INTO SEMANTIC.SEM_EPISODE_PARTICIPANTS
                (VIDEO_ID, PARTICIPANT_NAME, PARTICIPANT_ROLE, EXTRACTION_METHOD, CONFIDENCE, CHANNEL_NAME, EPISODE_TITLE)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, rows_to_insert)
        conn.commit()
        log.info("Done.")

    # Coverage report
    cur.execute("""
        SELECT
            COUNT(DISTINCT VIDEO_ID)                                                    AS total_episodes,
            COUNT(DISTINCT CASE WHEN PARTICIPANT_ROLE = 'GUEST' THEN VIDEO_ID END)     AS episodes_with_guest,
            ROUND(
                COUNT(DISTINCT CASE WHEN PARTICIPANT_ROLE = 'GUEST' THEN VIDEO_ID END)
                * 100.0 / NULLIF(COUNT(DISTINCT VIDEO_ID), 0), 1
            )                                                                           AS guest_coverage_pct
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
    """)
    row = cur.fetchone()
    log.info(
        f"\nCoverage: {row[1]}/{row[0]} episodes have a named guest ({row[2]}%)"
    )

    cur.close()
    conn.close()


if __name__ == "__main__":
    run()
