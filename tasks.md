# PodcastIQ - Detailed Implementation Tasks

**Project Timeline:** 8 Weeks (February - April 2026)
**Last Updated:** February 20, 2026
**Team Size:** 3 Members
**Target Scope:** 300+ Episodes | 18,000+ Segments

---

## 📅 Roadmap Overview

| Week | Focus | Status |
|------|-------|--------|
| 1 | Environment Setup + Steps 1-2 (Extract & Profile) | [x] Completed |
| 2 | Steps 3-6 (Stage, Load, Clean, Structure) | [/] In Progress |
| 3 | Steps 7-8 (Chunk & Enrich) | [ ] Not Started |
| 4 | Steps 9-10 (Index & Validate) + LangGraph MVP | [ ] Not Started |
| 5 | Streamlit UI + Topic Extraction Agent | [ ] Not Started |
| 6 | Comparison/Recommendation Agents + MCP | [ ] Not Started |
| 7 | Orchestration (Airflow), Testing & Optimization | [ ] Not Started |
| 8 | Final Presentation & Demo | [ ] Not Started |

---

## THE COMPLETE DATA ENGINEERING PIPELINE

```
STEP 1        STEP 2         STEP 3          STEP 4
EXTRACT       PROFILE        STAGE           LOAD
(Python)      (Python)       (Snowflake)     (Snowflake)

YouTube API → ydata-prof  →  PUT to       →  COPY INTO
→ JSON files  Validate       Internal        RAW tables
locally       completeness   Stage           (VARIANT)

STEP 5        STEP 6         STEP 7          STEP 8
CLEAN         STRUCTURE      CHUNK           ENRICH
(dbt)         (dbt)          (dbt)           (dbt+Cortex)

stg_ models → int_ models →  cur_ models →  sem_ models
Parse JSON    Join tables    120s chunks     Embeddings
Fix text      Type casting   Sentence-       Topics
Remove noise  Guest names    aligned         Entities
→ STAGING     → INTERMEDIATE → CURATED      → SEMANTIC

STEP 9        STEP 10
INDEX         VALIDATE
(Snowflake)   (dbt tests)

Cortex     →  dbt test
Search        Quality checks
Service       Completeness
setup
Hybrid search
→ SEARCHABLE  → PRODUCTION-READY
```

---

## 🛠️ STAGE 0: PROJECT SETUP & INFRASTRUCTURE (Week 1)

### 0.1 Repository Structure
- [x] Create project root at `D:\Projects\PodcastIQ\`
- [x] Initialize Git repository
- [x] Create core directories: `airflow/`, `dbt_podcastiq/`, `langgraph_agents/`, `streamlit_app/`, `sql/`
- [x] Create base documentation: `PRD.md`, `planning.md`, `tasks.md`, `claude.md`, `README.md`

### 0.2 Environment & Dependencies
- [x] Create virtual environment `venv\`
- [x] Research and finalize `requirements.txt` (Snowflake, Airflow, dbt, LangGraph, Streamlit, ydata-profiling)
- [x] Install dependencies inside `venv`

### 0.3 Configuration & Secrets
- [x] Create `.env` file (NEVER commit to git)
- [x] Add Snowflake credentials (one team member's primary account)
- [ ] Verify local connection to Snowflake via Python

### 0.4 Snowflake Infrastructure
- [ ] Create database `PODCASTIQ`
- [ ] Create schemas: `RAW`, `STAGING`, `INTERMEDIATE`, `CURATED`, `SEMANTIC`, `APP`
- [ ] Create warehouses: `LOADING_WH` (X-SMALL), `TRANSFORM_WH` (SMALL), `SEARCH_WH` (X-SMALL)
- [ ] Create internal stage: `@PODCASTIQ.RAW.JSON_STAGE`
- [ ] Set auto-suspend policies (60-300s)

---

## 📥 STEP 1: EXTRACT (Python) — Week 1

### 1.1 Channel Discovery
- [x] Finalize list of 28 channels across 6 genres (~270 episodes)
- [x] Create `scripts/channels.json` with channel IDs and configs
- [x] Document final channel list (Verified 26 channels, 240+ transcripts)

### 1.2 Metadata Extraction (YouTube Data API v3)
- [x] Set up Google Cloud Console project and API key
- [x] Implement metadata fetcher (Title, Channel, Date, Duration)
- [x] Add key to `.env`

### 1.3 Transcript Extraction (youtube-transcript-api)
- [x] Create `scripts/channel_extraction.py` for batch extraction
- [x] Verify timestamp precision and language detection (en only)
- [x] Extract all channels → JSON files stored locally in `data/raw/`

---

## 📊 STEP 2: PROFILE (Python) — Week 1-2

### 2.1 Data Profiling with ydata-profiling
- [x] Install `ydata-profiling` package
- [x] Create `scripts/advanced_profile.py` profiling script
- [x] Profile metadata JSON files (check completeness, null rates, distributions)
- [x] Profile transcript JSON files (word counts, language, timestamp coverage)
- [x] Generate HTML profiling reports → `reports/transcript_data_profile.html`
- [ ] Document data quality findings and any exclusions

---

## ☁️ STEP 3: STAGE (Snowflake) — Week 2

### 3.1 Internal Stage Setup
- [ ] Create named internal stage `@PODCASTIQ.RAW.JSON_STAGE`
- [ ] Create `scripts/stage_data.py` — PUT local JSON files to internal stage
- [ ] PUT metadata JSON files to stage
- [ ] PUT transcript JSON files to stage
- [ ] Verify staged files with `LIST @JSON_STAGE`

---

## 📦 STEP 4: LOAD (Snowflake) — Week 2

### 4.1 RAW Layer Loading
- [ ] Create `raw.raw_youtube_metadata` table (VARIANT column for JSON)
- [ ] Create `raw.raw_transcripts` table (VARIANT column for JSON)
- [ ] Create file format: `JSON_FORMAT` (type = JSON, strip_outer_array = true)
- [ ] Write COPY INTO statements for metadata
- [ ] Write COPY INTO statements for transcripts
- [ ] Create `sql/load_raw.sql` with all loading logic
- [ ] Verify row counts match source file counts
- [ ] Verify VARIANT data is queryable with `:` notation

---

## 🧹 STEP 5: CLEAN — dbt Staging Models (Week 2)

### 5.1 dbt Project Setup
- [ ] Initialize dbt project `dbt_podcastiq`
- [ ] Configure `profiles.yml` for Snowflake connection
- [ ] Create `dbt_project.yml` with model paths for staging/intermediate/curated/semantic

### 5.2 Staging Models (stg_)
- [ ] Create `models/staging/stg_youtube_metadata.sql`
  - Parse VARIANT JSON → flat columns (video_id, title, channel_name, published_at, duration_seconds, etc.)
  - Cast types (timestamps, integers)
  - Remove duplicates (dedup by video_id)
  - Add `_loaded_at` audit column
- [ ] Create `models/staging/stg_transcripts.sql`
  - Parse VARIANT JSON → flat columns (video_id, text, start_seconds, duration_seconds)
  - Fix text: trim whitespace, normalize unicode, remove `[Music]`/`[Applause]` noise markers
  - Filter out empty/null text segments
  - Add `_loaded_at` audit column
- [ ] Create `models/staging/schema.yml` with column descriptions and basic tests

---

## 🔗 STEP 6: STRUCTURE — dbt Intermediate Models (Week 2)

### 6.1 Intermediate Models (int_)
- [ ] Create `models/intermediate/int_episodes.sql`
  - Join metadata + transcripts (aggregate full transcript per episode)
  - Calculate derived fields: total_word_count, transcript_duration_seconds, has_transcript flag
  - Type casting and normalization
  - Extract guest names from title patterns (e.g., "with Guest Name", "ft. Guest Name")
- [ ] Create `models/intermediate/int_transcript_lines.sql`
  - Normalize transcript lines with episode context
  - Add cumulative word counts and sentence boundaries
  - Create sequential line numbering per episode
- [ ] Create `models/intermediate/schema.yml` with tests (not_null, unique, relationships)

---

## ✂️ STEP 7: CHUNK — dbt Curated Models (Week 3)

### 7.1 Curated Models (cur_)
- [ ] Create `models/curated/cur_episodes.sql`
  - Final cleaned episode records with all metadata
  - Materialized as TABLE for query performance
- [ ] Create `models/curated/cur_segments.sql`
  - Implement 120-second chunking windows (sentence-aligned boundaries)
  - Ensure chunks break at sentence boundaries (not mid-word)
  - Add overlap between adjacent chunks (~15-20s)
  - Generate YouTube deep links: `https://youtu.be/{video_id}?t={start_seconds}s`
  - Add `previous_segment_id` and `next_segment_id` for context retrieval
  - Calculate `word_count` per segment
  - Materialized as TABLE
- [ ] Create `models/curated/schema.yml` with tests
- [ ] Verify: avg segments per episode (~30-40 at 120s windows)
- [ ] Verify: chunk boundaries align with sentence endings

---

## 🧠 STEP 8: ENRICH — dbt Semantic Models (Week 3)

### 8.1 Embedding Generation
- [ ] Create `models/semantic/sem_embeddings.sql` (INCREMENTAL)
  - Use `SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', segment_text)`
  - Only process new/changed segments (incremental)
  - Store 768-dimensional vectors in VECTOR column type
  - Monitor credit usage during initial batch run

### 8.2 Topic & Entity Extraction
- [ ] Create `models/semantic/sem_topics_entities.sql` (INCREMENTAL)
  - Use `SNOWFLAKE.CORTEX.COMPLETE('llama3.1-405b', extraction_prompt)` for NER
  - Extract: people, organizations, technologies, topics
  - Store confidence scores for filtering
  - Parse LLM JSON output into structured columns

### 8.3 Episode Summaries
- [ ] Create `models/semantic/sem_episode_summaries.sql` (INCREMENTAL)
  - Generate multi-level summaries (1-sentence, paragraph, detailed)
  - Use Cortex LLM with curated episode text as input

### 8.4 Semantic Schema
- [ ] Create `models/semantic/schema.yml` with tests and docs

---

## 🔍 STEP 9: INDEX (Snowflake) — Week 4

### 9.1 Cortex Search Service
- [ ] Create `sql/cortex_search_setup.sql`
- [ ] Create Cortex Search service `podcast_search`:
  - Hybrid search (vector + keyword + LLM re-ranking)
  - Join embeddings ↔ segments ↔ episodes
  - Configure `TARGET_LAG = '2 minutes'`
- [ ] Test search quality with sample queries
- [ ] Verify search latency < 2 seconds

---

## ✅ STEP 10: VALIDATE (dbt tests) — Week 4

### 10.1 Data Quality Tests
- [ ] Add `not_null` tests on all critical columns (video_id, segment_text, embedding_vector)
- [ ] Add `unique` tests on primary keys (video_id, segment_id)
- [ ] Add `relationships` tests (segments → episodes, embeddings → segments)
- [ ] Create custom test: embedding coverage = 100% of segments
- [ ] Create custom test: all YouTube links match valid format
- [ ] Create custom test: segment timestamps are chronologically ordered per episode
- [ ] Run full `dbt test` suite — all tests must pass
- [ ] Document test results

---

## 🤖 MULTI-AGENT SYSTEM (Weeks 4-6)

### MVP Agents (Week 4)
- [ ] Define `PodcastIQState` TypedDict and LangGraph workflow graph
- [ ] Implement Router Agent (classify query → route to specialist)
- [ ] Implement Search Agent (Cortex Search integration + adjacent segment fetch)
- [ ] Implement Summarization Agent (generate answers with YouTube refs)
- [ ] Test end-to-end: User query → Router → Search → Summary

### Backend (Week 4)
- [ ] Configure Python client for Snowflake Cortex LLM functions

### Stretch Agents (Week 6)
- [ ] Implement Topic Extraction Agent
- [ ] Implement Comparison Agent (cross-podcast analysis)
- [ ] Implement Recommendation Agent (content-based filtering)

### MCP Integration (Week 6)
- [ ] Set up Filesystem + Web Search MCP servers
- [ ] Integrate MCP tools into LangGraph workflow

---

## 🖥️ USER INTERFACE (Week 5)

### Streamlit App
- [ ] Build search bar and result card components
- [ ] Implement sidebar filters (Topic, Channel, Date)
- [ ] Add "Click to Play" YouTube timestamp links
- [ ] Implement "Context Expansion" to show surrounding segments

---

## 🗓️ ORCHESTRATION (Week 7)

### Airflow DAGs
- [ ] Create `youtube_extract_dag.py` (extraction pipeline)
- [ ] Create `dbt_transform_dag.py` (run dbt models post-ingestion)
- [ ] Create `embedding_generation_dag.py` (weekly embedding refresh)
- [ ] Set up alerting for DAG failures

---

## 🚀 DEPLOYMENT & PRESENTATION (Week 8)

### Final Demo
- [ ] Prepare demo script with 5 key queries
- [ ] Create slide deck (problem, solution, architecture, challenges, learnings)
- [ ] Record backup demo video
- [ ] Finalize documentation and repository cleanup
- [ ] Final report (5-10 pages)

---

## 📝 Current Focus: Week 2
**Goal:** Complete Steps 3-6 (Stage → Structure)

**Completed:**
- Step 1: Batch extraction of 26 channels (250+ episodes in `data/raw/`)
- Step 2: Data profiling with ydata-profiling (report at `reports/transcript_data_profile.html`)
- Environment setup, `.env`, `requirements.txt`

**Next Up:**
- Snowflake infrastructure setup — run `sql/schema_setup.sql` (schemas, stages, warehouses)
- Stage & Load JSON data into Snowflake RAW (Steps 3-4)
- dbt project init + staging/intermediate models (Steps 5-6)

**Blockers:** None

---

## 📊 Progress Tracking

| Week | Status | Start Date | End Date | Notes |
|------|--------|------------|----------|-------|
| 1 | Completed | Feb 15 | Feb 20 | Steps 1-2 done: 250+ episodes extracted, profiling report generated |
| 2 | Not Started | - | - | |
| 3 | Not Started | - | - | |
| 4 | Not Started | - | - | |
| 5 | Not Started | - | - | |
| 6 | Not Started | - | - | |
| 7 | Not Started | - | - | |
| 8 | Not Started | - | - | |
