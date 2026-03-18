# PodcastIQ Implementation Plan (Expanded)

## Context

**Problem:** Over 5 million podcasts exist, but audio content is unsearchable. Users waste hours listening to entire episodes to find specific discussions, and valuable insights remain buried in audio format.

**Solution:** PodcastIQ - An AI-powered podcast **intelligence platform** that makes podcast content searchable, tracks how claims evolve over time, and automatically fact-checks podcast statements using a temporal knowledge graph, multi-agent orchestration, and hybrid RAG architecture (vector search + graph traversal).

**What Makes This Novel:**
- **GraphRAG** — Combines vector search (Cortex Search) with graph traversal (Neo4j) for relationship reasoning. Based on Microsoft Research's 2024 GraphRAG pattern.
- **Temporal Knowledge Graph** — Tracks how claims and opinions evolve across episodes and speakers over time. Detects opinion drift, revised predictions, and contradictions.
- **Hybrid Fact-Checking** — Two-stage verification pipeline: Cortex LLM pre-filter + MCP web search for uncertain claims. Cost-optimized (~60-70% resolved without API calls).
- **Two-Tier Speaker Attribution** — Metadata extraction + LLM inference with explicit confidence scoring for claim attribution without audio diarization.

**Course Requirements Met:**
1. ✅ Data Engineering: ETL/ELT pipeline extracting YouTube transcripts → transforming via Snowflake SQL → loading to Snowflake (Steps 1–9 complete)
2. ✅ Generative AI: Multi-agent system with 9 specialized agents using Snowflake Cortex LLMs
3. ✅ RAG Implementation: Hybrid RAG — vector embeddings via Cortex Search + graph traversal via Neo4j (GraphRAG pattern)
4. ✅ Agentic AI Architecture: LangGraph orchestrating Router, Search, Summarization, Knowledge Graph, Temporal Analysis, Fact-Check, Comparison, Recommendation, and Insight agents
5. ✅ MCP Integration: Fact-checking agent uses MCP Web Search server for real-time claim verification

---

## High-Level Architecture

```
YouTube API (25 channels, 290+ episodes, 6 genres)
          ↓
   channel_extraction.py (yt-dlp + YouTube Data API v3)
   → data/raw/{channel}/{video_id}_metadata.json
   → data/raw/{channel}/{video_id}_transcript.json
          ↓
   snowflake_loader.py (PUT → COPY INTO)
          ↓
   Snowflake (6-Schema Data Warehouse)
   ├── RAW:          EPISODES (VARIANT), CHANNELS
   ├── STAGING:      STG_EPISODES, STG_SEGMENTS (views)
   │                 INT_EPISODES, INT_SEGMENTS  (views)
   ├── CURATED:      CUR_CHUNKS (120s windows, ~250K chunks)
   ├── SEMANTIC:     SEM_CHUNK_EMBEDDINGS (VECTOR 768-dim)
   │                 SEM_CHUNK_TOPICS, SEM_CHUNK_ENTITIES
   │                 SEM_EPISODE_SUMMARIES
   │                 SEM_CLAIMS (extracted claims with speaker attribution)
   │                 SEM_CLAIM_EVOLUTION (temporal drift tracking)
   │                 SEM_EPISODE_PARTICIPANTS (host/guest per episode)
   ├── APP:          search_history, user_preferences
   └── Cortex Search: PODCASTIQ_SEARCH (hybrid search service) ✅ LIVE
          ↓
   Claim Extraction Pipeline
   ├── Cortex LLM extracts structured claims from chunks
   ├── Two-tier speaker attribution (metadata + LLM inference)
   ├── Claim classification (VERIFIABLE_FACT / PREDICTION / OPINION / STATISTICAL)
   └── Claims stored in SEM_CLAIMS table
          ↓
   Neo4j Knowledge Graph
   ├── Nodes: Person, Organization, Topic, Episode, Channel, Claim
   ├── Edges: MADE_CLAIM, APPEARED_ON, DISCUSSED, EVOLVED_FROM, etc.
   ├── Entity resolution (merge duplicate names)
   └── Claim linking + drift detection
          ↓
   Hybrid Fact-Checking Pipeline
   ├── Stage 1: Cortex LLM pre-filter (resolve ~30-40% from training knowledge)
   ├── Stage 2: MCP Web Search for uncertain claims (Brave Search API)
   ├── Stage 3: Cortex LLM synthesizes final verdict
   └── Results: VERIFIED / OUTDATED / DISPUTED / UNVERIFIED / FALSE
          ↓
   LangGraph Multi-Agent System (9 Agents)
   ├── Router Agent (orchestration)
   ├── Search Agent (hybrid: Cortex Search + Neo4j)
   ├── Summarization Agent (answers + YouTube links + claim status)
   ├── Knowledge Graph Agent (Cypher queries)
   ├── Temporal Analysis Agent (claim evolution + drift detection)
   ├── Fact-Check Agent (hybrid: Cortex LLM + MCP web search)
   ├── Comparison Agent (graph-powered cross-podcast)
   ├── Recommendation Agent (graph-based suggestions)
   └── Insight Agent (credibility scores, debate detection)
          ↑
   MCP Servers
   ├── Web Search MCP (Brave Search API for fact-checking)
   ├── Filesystem MCP (read transcripts, logs)
   └── Database MCP (query Snowflake directly)
          ↓
   Streamlit UI
   ├── Search + Results with verification badges
   ├── Interactive Knowledge Graph Explorer
   ├── Claim Timeline View (temporal evolution)
   ├── Channel Credibility Dashboard
   └── Episode Detail with per-claim fact-check status
```

---

## Technology Stack

| Component | Technology | Status | Purpose |
|-----------|-----------|--------|---------|
| Data Warehouse | Snowflake | ✅ Live | Storage, compute, vector search |
| LLM/AI | Snowflake Cortex | ✅ Live | llama3.1-405b for reasoning, Arctic Embed for embeddings |
| Transcript Extraction | yt-dlp + YouTube Data API v3 | ✅ Live | Download WebVTT subtitles + metadata |
| Data Loading | Python `snowflake_loader.py` | ✅ Live | PUT + COPY INTO RAW layer (key-pair auth) |
| Transformation | Snowflake SQL Views + Cortex AI | ✅ Live | STAGING views, CURATED chunks, SEMANTIC enrichment |
| Search | Snowflake Cortex Search | ✅ Live | Hybrid vector + keyword + LLM re-ranking |
| Graph Database | Neo4j Community Edition | ⏳ Week 5 | Knowledge graph storage + Cypher queries |
| Graph Integration | neo4j Python driver | ⏳ Week 5 | Connect LangGraph agents to Neo4j |
| Graph Visualization | neovis.js or react-force-graph | ⏳ Week 8 | Interactive graph explorer in UI |
| Agent Framework | LangGraph | ⏳ Week 4 | Multi-agent state machines |
| Frontend | Streamlit | ⏳ Week 8 | Interactive search + graph + timeline UI |
| MCP Servers | @modelcontextprotocol/sdk | ⏳ Week 7 | Web Search for fact-checking |
| Orchestration | Apache Airflow (local via Astro CLI) | ⏳ Week 9 | ETL automation, scheduling |

**Cost:** <$100 additional — University Snowflake access + free Neo4j CE + free Brave Search tier

---

## Snowflake Schema Design

### Existing Layers (Complete ✅)

**Layer 1: RAW** ✅
- `RAW.EPISODES` — One row per video. `RAW_DATA VARIANT` (full merged payload). PK: `VIDEO_ID`
- `RAW.CHANNELS` — One row per channel. `CHANNEL_ID`, `CHANNEL_NAME`, `GENRE`, `YOUTUBE_URL`

**Layer 2: STAGING** ✅ (all views)
- `STAGING.STG_EPISODES` — Parses VARIANT → 22 flat typed columns
- `STAGING.STG_SEGMENTS` — LATERAL FLATTEN → one row per transcript line
- `STAGING.INT_EPISODES` — Joins STG_EPISODES + CHANNELS. Adds TRANSCRIPT_QUALITY, ENGAGEMENT_RATE
- `STAGING.INT_SEGMENTS` — Adds YOUTUBE_TIMESTAMP_URL, WORD_COUNT

**Layer 3: CURATED** ✅
- `CURATED.CUR_CHUNKS` — 120-second windowed chunks. CHUNK_ID, CHUNK_TEXT, YOUTUBE_URL, WORD_COUNT

**Layer 4: SEMANTIC** ✅ (existing) + new tables
- `SEM_CHUNK_EMBEDDINGS` — VECTOR(FLOAT, 768) per chunk ✅
- `SEM_CHUNK_TOPICS` — LLM-extracted topics ✅
- `SEM_CHUNK_ENTITIES` — NER (people, orgs, tech) ✅
- `SEM_EPISODE_SUMMARIES` — Episode-level summaries ✅
- `PODCASTIQ_SEARCH` — Cortex Search service (live since Feb 21) ✅

**Layer 5: APP** (Weeks 8-9)
- `APP.SEARCH_HISTORY` — Query logs
- `APP.USER_PREFERENCES` — Saved episodes, favorite topics

### New Tables (To Build)

**SEM_EPISODE_PARTICIPANTS** (Week 4)
```sql
CREATE TABLE SEMANTIC.SEM_EPISODE_PARTICIPANTS (
    VIDEO_ID VARCHAR,
    PARTICIPANT_NAME VARCHAR(200),
    PARTICIPANT_ROLE VARCHAR(20),         -- HOST / GUEST
    EXTRACTION_METHOD VARCHAR(20),        -- TITLE_PARSE / MANUAL / LLM_INFERRED
    CONFIDENCE VARCHAR(20),
    PRIMARY KEY (VIDEO_ID, PARTICIPANT_NAME)
);
```

**SEM_CLAIMS** (Week 4)
```sql
CREATE TABLE SEMANTIC.SEM_CLAIMS (
    CLAIM_ID VARCHAR PRIMARY KEY,
    CHUNK_ID VARCHAR NOT NULL,
    VIDEO_ID VARCHAR NOT NULL,
    CLAIM_TEXT VARCHAR(2000),
    SPEAKER VARCHAR(200),
    SPEAKER_ROLE VARCHAR(20),            -- HOST / GUEST / UNKNOWN
    ATTRIBUTION_CONFIDENCE VARCHAR(20),  -- HIGH / MEDIUM / LOW / UNKNOWN
    ATTRIBUTION_SOURCE VARCHAR(20),      -- METADATA / LLM_INFERRED / EPISODE_LEVEL
    TOPIC VARCHAR(500),
    CLAIM_TYPE VARCHAR(50),              -- VERIFIABLE_FACT / PREDICTION / OPINION / STATISTICAL
    SENTIMENT VARCHAR(20),
    CONFIDENCE VARCHAR(20),
    CLAIM_DATE DATE,
    YOUTUBE_URL VARCHAR(500),
    VERIFICATION_STATUS VARCHAR(20) DEFAULT 'PENDING',
    VERIFICATION_SOURCE VARCHAR(20),     -- LLM_ONLY / LLM_PLUS_WEB / PENDING
    LAST_VERIFIED TIMESTAMP,
    EVIDENCE_SUMMARY VARCHAR(2000),
    EVIDENCE_URLS ARRAY,
    EXTRACTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    EXTRACTION_MODEL VARCHAR(50) DEFAULT 'llama3.1-405b'
);
```

**SEM_CLAIM_EVOLUTION** (Week 6)
```sql
CREATE TABLE SEMANTIC.SEM_CLAIM_EVOLUTION (
    EVOLUTION_ID VARCHAR PRIMARY KEY,
    ORIGINAL_CLAIM_ID VARCHAR,
    EVOLVED_CLAIM_ID VARCHAR,
    DRIFT_TYPE VARCHAR(20),              -- REVISED / ESCALATED / SOFTENED / CONTRADICTED / CONFIRMED
    SAME_SPEAKER BOOLEAN,
    TIME_DELTA_DAYS INTEGER,
    ANALYSIS VARCHAR(1000),
    DETECTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

---

## Neo4j Knowledge Graph Schema

### Node Types
```cypher
(:Person {name, aliases, first_seen, episode_count})
(:Organization {name, type, founded_year})
(:Topic {name, category, first_mentioned})
(:Episode {video_id, title, publish_date, channel_name, youtube_url})
(:Channel {channel_id, name, genre})
(:Claim {
    claim_id, text, type, sentiment, confidence, date,
    chunk_id, youtube_url,
    verification_status, verification_source, last_verified, evidence_summary
})
```

### Edge Types
```cypher
(Person)-[:APPEARED_ON {role: "host"|"guest"}]->(Episode)
(Person)-[:WORKS_AT {since, until}]->(Organization)
(Person)-[:MADE_CLAIM {confidence: "HIGH"}]->(Claim)
(Person)-[:LIKELY_MADE_CLAIM {confidence: "MEDIUM"}]->(Claim)
(Episode)-[:BELONGS_TO]->(Channel)
(Episode)-[:DISCUSSED {depth}]->(Topic)
(Claim)-[:ABOUT]->(Topic)
(Claim)-[:MENTIONS]->(Person|Organization)
(Claim)-[:DISCUSSED_IN]->(Episode)          -- unknown speaker fallback
(Claim)-[:EVOLVED_FROM {drift_type}]->(Claim)
(Claim)-[:SOURCED_FROM]->(Episode)
```

---

## Two-Tier Speaker Attribution

### Tier 1: Metadata Extraction (100% confident)
- Host = channel owner (always known, hardcoded per channel)
- Guest = parsed from episode title via regex + LLM fallback
- Channel-specific title patterns:
  - Lex Fridman: `"Sam Altman: Future of AI | Lex Fridman Podcast #412"`
  - Joe Rogan: `"#2108 - Sam Altman"`
  - Huberman Lab: `"Dr. Peter Attia: Exercise & Longevity"`
  - My First Million: `"Shaan Puri on Why Every Founder..."`
  - All-In: 4 fixed hosts (Calacanis, Sacks, Chamath, Friedberg)
- Expected coverage: ~70-80% of episodes get a named guest

### Tier 2: LLM Speaker Inference (per-claim, during claim extraction)
- Same LLM call as claim extraction (zero extra cost)
- Prompt includes known participants from Tier 1
- Context clues: personal anecdotes, role references, question/answer patterns
- Each claim gets `attribution_confidence`: HIGH / MEDIUM / LOW / UNKNOWN

### Graph Mapping
- HIGH confidence → `(Person)-[:MADE_CLAIM]->(Claim)`
- MEDIUM confidence → `(Person)-[:LIKELY_MADE_CLAIM]->(Claim)`
- UNKNOWN → `(Claim)-[:DISCUSSED_IN]->(Episode)`

---

## Hybrid Fact-Checking Pipeline

### Stage 1: Cortex LLM Pre-Filter (free, fast, no rate limits)
- Run every VERIFIABLE_FACT and STATISTICAL claim through Cortex LLM
- Prompt: "Based on your knowledge, is this claim true, false, or uncertain?"
- Confident results → marked immediately
- Uncertain results → flagged for Stage 2
- Expected: ~30-40% resolved at this stage

### Stage 2: MCP Web Search (for uncertain claims only)
- Fact-Check Agent formulates search query from claim
- MCP Web Search server (Brave Search API, free tier: 2,000 queries/month)
- Returns top web results with current information

### Stage 3: LLM Verdict Synthesis
- Cortex LLM reads web results + original claim
- Assigns final status: VERIFIED / OUTDATED / DISPUTED / UNVERIFIED / FALSE
- Generates evidence summary + source URLs
- Results written to SEM_CLAIMS + Neo4j Claim nodes

---

## Data Re-Extraction Plan (Time-Stratified)

### Problem
Original extraction sorted by view count → popular episodes cluster in late 2025. 10 channels have <7 month date spans.

### Solution
Re-extract ~40 episodes for 6 channels: 2-3 episodes per year (2022-2024), keeping existing 2025 episodes.

### Priority 1 — Must Fix
| Channel | Current Span | Add 2022 | Add 2023 | Add 2024 | New Eps |
|---------|-------------|----------|----------|----------|---------|
| All-In Podcast | 4 months | +3 | +3 | +2 | 8 |
| a16z Podcast | 5 months | +2 | +3 | +3 | 8 |
| Joe Rogan (tech guests) | 4 months | +2 | +2 | +2 | 6 |

### Priority 2 — High Value
| Channel | Current Span | Add 2022 | Add 2023 | Add 2024 | New Eps |
|---------|-------------|----------|----------|----------|---------|
| My First Million | 6 months | +2 | +2 | +2 | 6 |
| Diary of a CEO | 6 months | +2 | +2 | +2 | 6 |
| Huberman Lab | 7 months | +2 | +2 | +2 | 6 |

### Extraction Strategy
```python
for year in [2022, 2023, 2024]:
    publishedAfter = f"{year}-01-01T00:00:00Z"
    publishedBefore = f"{year}-12-31T23:59:59Z"
    # Fetch top 2-3 by viewCount within this year range
```

### Post Re-Extraction Targets
- Total episodes: ~290 (250 existing + 40 new)
- All priority channels: 20+ month spans
- 20+ channels with 12+ month spans

---

## Expanded Agent Architecture (9 Agents)

### MVP Agents (Week 4)
1. **Router Agent** — Classifies query → routes to specialist
2. **Search Agent** — Hybrid: Cortex Search + Neo4j traversal
3. **Summarization Agent** — Generates answers with YouTube links + claim status

### Knowledge Graph Agents (Weeks 5-6)
4. **Knowledge Graph Agent** — Cypher queries for relationship reasoning
5. **Temporal Analysis Agent** — Claim evolution tracking + drift detection
6. **Comparison Agent** — Graph-powered cross-podcast analysis

### Fact-Check + Insight Agents (Week 7)
7. **Fact-Check Agent** — Hybrid: Cortex LLM pre-filter + MCP web search
8. **Recommendation Agent** — Graph-based content suggestions
9. **Insight Agent** — Meta-analysis: credibility scores, debate detection

---

## Key Design Decisions

### 1. GraphRAG: Cortex Search + Neo4j
Vector search finds semantically similar content; graph traversal finds relationship-based content. Combined = GraphRAG (Microsoft Research 2024). Enables queries pure vector search cannot answer.

### 2. Two-Tier Speaker Attribution
No audio diarization needed. Zero extra LLM cost. Explicit confidence scoring models uncertainty honestly. Future path: add Whisper diarization.

### 3. Hybrid Fact-Checking
Reduces API costs by ~60-70%. Satisfies both Cortex AI and MCP course requirements. MCP provides freshness LLM training data lacks.

### 4. Time-Stratified Re-Extraction
Original extraction clustered in 2025. Targeted re-extraction (~40 episodes, ~3-4 hours) fixes temporal gaps with minimal effort.

### 5. 120-Second Time-Based Chunking
Preserves YouTube deep linking. Consistent chunk sizes. Simple implementation.

### 6. Neo4j Community Edition (Local Docker)
Free. Full Cypher query language. Easy Python integration. Docker install = 10 minutes.

---

## Cost Management

### Snowflake Credit Budget
- Original pipeline: ~248 credits (estimated)
- Re-extraction enrichment: ~15 credits
- Claim extraction (LLM calls on ~20K chunks): ~20-30 credits
- Ongoing queries/development: ~50 credits
- **Total estimated: ~340 credits** (within 3-account budget of 600 credits)

### New Components (Free)
- Neo4j Community Edition: Free (local Docker)
- Brave Search API: Free tier (2,000 queries/month)
- LangGraph: Free (open source)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Neo4j learning curve | MEDIUM | Budget 1 full day. Cypher is similar to SQL. Docker install = 10 min. |
| Claim extraction quality | MEDIUM | Start with high-confidence claims only. Structured prompts with examples. Accept 70-80% accuracy. |
| Fact-checking rate limits | LOW | Cortex LLM pre-filter resolves ~30-40% first, reducing web searches needed. |
| Temporal evolution sparse for some topics | LOW | Focus on topic-level evolution (across speakers), not just individual speaker changes. |
| Re-extraction pipeline issues | LOW | Pipeline already tested and working. MERGE handles dedup. ~3-4 hours total. |
| Scope creep (9 agents ambitious) | MEDIUM | Hard prioritize: MVP agents (W4) > Graph (W5) > Temporal (W6) > Fact-check (W7). Cut Insight Agent if behind. |
| Neo4j + Snowflake sync | LOW | Snowflake = source of truth. Neo4j = read-optimized projection. One-way sync. |
| Timeline (11 weeks vs 8) | MEDIUM | Core pipeline done. Extra weeks go entirely to novel features. Cut Priority 3 re-extraction if behind. |

---

## Demo Script (Week 11)

1. **Basic Search:** "How do large language models work?" → Summary + YouTube links
2. **Knowledge Graph:** "Who has Sam Altman appeared with?" → Graph visualization
3. **Temporal Evolution:** "How have AGI timeline predictions changed 2022-2025?" → Claim timeline
4. **Fact-Checking:** "Are there outdated claims in Huberman Lab episodes?" → Verification badges
5. **Cross-Podcast Comparison:** "Compare Lex Fridman and Joe Rogan on AI safety" → Graph analysis
6. **Credibility Insight:** "Which channels have highest fact-check accuracy?" → Dashboard
7. **Influence Network:** "Show the network around 'scaling laws'" → Interactive graph

---

## Future Enhancements (Post-Project)

1. Speaker diarization via Whisper + pyannote (ground truth for attribution)
2. Multi-language support
3. Audio clip generation (shareable clips from timestamp links)
4. Chrome extension (search while watching YouTube)
5. Custom MCP server (expose PodcastIQ search as tool for other LLM apps)
6. Real-time podcast monitoring (auto-ingest new episodes daily)
7. Episodic memory for personalized user experience across sessions
8. Collaborative filtering for recommendations (requires user accounts)

---

## Critical Files

### Completed ✅
1. `scripts/channel_extraction.py` — yt-dlp + YouTube API extraction
2. `scripts/snowflake_loader.py` — PUT + COPY INTO with key-pair auth
3. `scripts/advanced_profile.py` — ydata-profiling data quality report
4. `sql/schema_setup.sql` — Database, schemas, warehouses DDL
5. `sql/ddl/raw/` — EPISODES + CHANNELS DDL
6. `sql/ddl/staging/` — STG_EPISODES, STG_SEGMENTS views
7. `sql/ddl/intermediate/` — INT_EPISODES, INT_SEGMENTS views
8. `sql/ddl/curated/` — CUR_CHUNKS table DDL
9. `sql/ddl/semantic/` — SEM_CHUNK_EMBEDDINGS, TOPICS, ENTITIES, SUMMARIES DDL
10. `sql/pipeline_verification.sql` — Health check queries

### To Build
11. `scripts/time_stratified_extraction.py` — Re-extraction for 6 channels (Week 4)
12. `sql/ddl/semantic/sem_claims.sql` — Claims table DDL (Week 4)
13. `sql/ddl/semantic/sem_episode_participants.sql` — Participants DDL (Week 4)
14. `sql/ddl/semantic/sem_claim_evolution.sql` — Evolution DDL (Week 6)
15. `langgraph_agents/state.py` — PodcastIQState TypedDict (Week 4)
16. `langgraph_agents/graph.py` — LangGraph StateGraph workflow (Week 4)
17. `langgraph_agents/agents/router.py` — Query intent classification (Week 4)
18. `langgraph_agents/agents/search.py` — Cortex Search + Neo4j hybrid (Week 4)
19. `langgraph_agents/agents/summarization.py` — Cortex LLM answers (Week 4)
20. `langgraph_agents/agents/knowledge_graph.py` — Cypher queries (Week 5)
21. `langgraph_agents/agents/temporal.py` — Claim evolution (Week 6)
22. `langgraph_agents/agents/fact_check.py` — Hybrid verification (Week 7)
23. `langgraph_agents/agents/comparison.py` — Cross-podcast (Week 7)
24. `langgraph_agents/agents/recommendation.py` — Graph-based (Week 7)
25. `langgraph_agents/agents/insight.py` — Meta-analysis (Week 7)
26. `scripts/neo4j_loader.py` — Load claims → Neo4j (Week 5)
27. `scripts/claim_extractor.py` — LLM claim extraction pipeline (Week 4)
28. `scripts/guest_extractor.py` — Title parsing + LLM guest names (Week 4)
29. `scripts/fact_checker.py` — Batch verification pipeline (Week 7)
30. `streamlit_app/app.py` — Main UI (Week 8)
31. `airflow/dags/youtube_extract_dag.py` — Extraction DAG (Week 9)
32. `airflow/dags/claim_extraction_dag.py` — Claim + Neo4j DAG (Week 9)
33. `airflow/dags/fact_check_dag.py` — Weekly fact-check refresh (Week 9)