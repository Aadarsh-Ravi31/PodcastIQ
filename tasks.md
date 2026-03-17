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
| 2 | Steps 3-6 (Stage, Load, Clean, Structure) | [x] Completed |
| 3 | Steps 7-8 (Chunk & Enrich) | [x] Completed |
| 4 | Steps 9-10 (Index & Validate) + LangGraph MVP | [/] In Progress |
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
- [x] Create database `PODCASTIQ`
- [x] Create schemas: `RAW`, `STAGING`, `INTERMEDIATE`, `CURATED`, `SEMANTIC`, `APP`
- [x] Create warehouses: `LOADING_WH` (X-SMALL), `TRANSFORM_WH` (SMALL), `SEARCH_WH` (X-SMALL)
- [x] Create internal stage: `@PODCASTIQ.RAW.JSON_STAGE`
- [x] Set auto-suspend policies (60-300s)

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
- [x] Create named internal stage `@PODCASTIQ.RAW.JSON_STAGE`
- [x] Create `scripts/stage_data.py` — PUT local JSON files to internal stage
- [x] PUT metadata JSON files to stage
- [x] PUT transcript JSON files to stage
- [x] Verify staged files with `LIST @JSON_STAGE`

---

## 📦 STEP 4: LOAD (Snowflake) — Week 2

### 4.1 RAW Layer Loading
- [x] Create `raw.raw_youtube_metadata` table (VARIANT column for JSON)
- [x] Create `raw.raw_transcripts` table (VARIANT column for JSON)
- [x] Create file format: `JSON_FORMAT` (type = JSON, strip_outer_array = true)
- [x] Write COPY INTO statements for metadata
- [x] Write COPY INTO statements for transcripts
- [x] Create `sql/load_raw.sql` with all loading logic
- [x] Verify row counts match source file counts
- [x] Verify VARIANT data is queryable with `:` notation

---

## 🧹 STEP 5: CLEAN — dbt Staging Models (Week 2)

### 5.1 dbt Project Setup
- [x] Initialize dbt project `dbt_podcastiq`
- [x] Configure `profiles.yml` for Snowflake connection
- [x] Create `dbt_project.yml` with model paths for staging/intermediate/curated/semantic

### 5.2 Staging Models (stg_)
- [x] Create `models/staging/stg_youtube_metadata.sql`
- [x] Create `models/staging/stg_transcripts.sql`
- [x] Create `models/staging/schema.yml` with column descriptions and basic tests

---

## 🔗 STEP 6: STRUCTURE — dbt Intermediate Models (Week 2)

### 6.1 Intermediate Models (int_)
- [x] Create `models/intermediate/int_episodes.sql`
- [x] Create `models/intermediate/int_transcript_lines.sql`
- [x] Create `models/intermediate/schema.yml` with tests (not_null, unique, relationships)

---

## ✂️ STEP 7: CHUNK — dbt Curated Models (Week 3)

### 7.1 Curated Models (cur_)
- [x] Create `models/curated/cur_episodes.sql`
- [x] Create `models/curated/cur_chunks.sql` (chunked segments table — CUR_CHUNKS in Snowflake)
- [x] Create `models/curated/schema.yml` with tests
- [x] Verify chunking output in Snowflake

---

## 🧠 STEP 8: ENRICH — dbt Semantic Models (Week 3)

### 8.1 Embedding Generation
- [x] Create `models/semantic/sem_chunk_embeddings.sql` → `SEM_CHUNK_EMBEDDINGS` in Snowflake

### 8.2 Topic & Entity Extraction
- [x] Create `models/semantic/sem_chunk_topics.sql` → `SEM_CHUNK_TOPICS` in Snowflake
- [x] Create `models/semantic/sem_chunk_entities.sql` → `SEM_CHUNK_ENTITIES` in Snowflake

### 8.3 Episode Summaries
- [x] Create `models/semantic/sem_episode_summaries.sql` → `SEM_EPISODE_SUMMARIES` in Snowflake

### 8.4 Semantic Schema
- [ ] Create `models/semantic/schema.yml` with tests and docs

---

## 🔍 STEP 9: INDEX (Snowflake) — Week 4

### 9.1 Cortex Search Service
- [x] Create `sql/cortex_search_setup.sql`
- [x] Create Cortex Search service `PODCASTIQ_SEARCH` (live in SEMANTIC schema since Feb 21)
- [ ] Test search quality with sample queries (use `pipeline_verification.sql`)
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

## 📝 Current Focus: Week 3
**Goal:** Complete Step 8 (Enrich — Embeddings, Topics, Summaries) then Step 9 (Index — Cortex Search)

**Completed:**
- Steps 1-2: Batch extraction of 26 channels (250+ episodes), data profiling report
- Steps 3-4: Snowflake infrastructure, staged + loaded JSON to RAW layer
- Steps 5-6: dbt stg_ and int_ models (clean, structure)
- Step 7: dbt cur_ models — CUR_CHUNKS table live in Snowflake ✅

**Next Up:**
- Step 8: Generate embeddings with `SNOWFLAKE.CORTEX.EMBED_TEXT_768` → `sem_embeddings` table
- Step 8: Topic & entity extraction via Cortex LLM → `sem_topics_entities` table
- Step 8: Episode summaries via Cortex LLM → `sem_episode_summaries` table
- Step 9: Create Cortex Search service on `sem_embeddings` + `cur_chunks`
- Step 10: dbt tests for data quality validation

**Blockers:** None

---

## 📊 Progress Tracking

| Week | Status | Start Date | End Date | Notes |
|------|--------|------------|----------|-------|
| 1 | Completed | Feb 15 | Feb 20 | Steps 1-2 done: 250+ episodes extracted, profiling report generated |
| 2 | Completed | - | Mar 17 | Steps 3-6 done: RAW loaded, stg/int dbt models complete |
| 3 | Completed | Mar 17 | Mar 17 | Steps 7-8 done: CUR_CHUNKS, SEM embeddings/topics/entities/summaries all live |
| 4 | In Progress | Mar 17 | - | PODCASTIQ_SEARCH service live; LangGraph agents next |
| 5 | Not Started | - | - | |
| 6 | Not Started | - | - | |
| 7 | Not Started | - | - | |
| 8 | Not Started | - | - | |
