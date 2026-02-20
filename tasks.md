# PodcastIQ - Detailed Implementation Tasks

**Project Timeline:** 8 Weeks (February - April 2026)
**Last Updated:** February 19, 2026
**Team Size:** 3 Members
**Target Scope:** 300+ Episodes | 18,000+ Segments

---

## 📅 Roadmap Overview

| Week | Stage | Focus | Status |
|------|-------|-------|--------|
| 1 | 0 & 1 | Environment Setup + POC Extraction | [/] In Progress |
| 2 | 2 & 3 | ETL Pipeline & DBT (300 Episodes) | [ ] Not Started |
| 3 | 4 | Semantic enrichment (Embeddings + Cortex Search) | [ ] Not Started |
| 4 | 5 (MVP) | LangGraph Agents (Router, Search, Summary) | [ ] Not Started |
| 5 | 7 | Streamlit UI + Topic Extraction | [ ] Not Started |
| 6 | 5 (Stretch) & 5.3 | Comparison/Recommendation Agents + MCP | [ ] Not Started |
| 7 | 8 & 9 | Orchestration, Testing & Optimization | [ ] Not Started |
| 8 | 10 | Final Presentation & Demo | [ ] Not Started |

---

## 🛠️ STAGE 0: PROJECT SETUP & INFRASTRUCTURE (Week 1)

### 0.1 Repository Structure (Method C: Modular Monorepo)
- [x] Create project root at `D:\Projects\PodcastIQ\`
- [x] Initialize Git repository
- [x] Create core directories: `airflow/`, `dbt_podcastiq/`, `langgraph_agents/`, `streamlit_app/`, `sql/`
- [x] Create base documentation: `PRD.md`, `planning.md`, `tasks.md`, `claude.md`, `README.md`

### 0.2 Environment & Dependencies (Method A: venv + requirements.txt)
- [x] Create virtual environment `venv\`
- [ ] Research and finalize `requirements.txt` (Snowflake, Airflow, dbt, LangGraph, Streamlit)
- [ ] Install dependencies inside `venv`

### 0.3 Configuration & Secrets (Method A: .env)
- [ ] Create `.env` file (NEVER commit to git)
- [ ] Add Snowflake credentials (one team member's primary account)
- [ ] Verify local connection to Snowflake via Python

---

## 🎙️ STAGE 1: DATA EXTRACTION (Week 1-2)

### 1.1 Transcript Extraction (Method A: youtube-transcript-api)
- [x] Select 5 POC episodes (tech/AI)
- [x] Build proof-of-concept Python script for extraction
- [x] Verify timestamp precision and language detection (en only)

### 1.2 Metadata Extraction (Method A: YouTube Data API v3)
- [x] Set up Google Cloud Console project and API key
- [x] Implement metadata fetcher (Title, Channel, Date, Duration)
- [x] Add key to `.env`

### 1.3 Channel Discovery (Method A: Manual Curation)
- [x] Finalize list of 28 channels across 6 genres (~270 episodes)
- [x] Create `scripts/channels.json` with channel IDs and configs
- [x] Create `scripts/channel_extraction.py` for batch extraction
- [ ] Document final channel list in `PRD.md`

---

## 📥 STAGE 2: DATA LOADING (Week 2)

### 2.1 Loading Method (Method A: Snowflake Direct INSERT/MERGE)
- [ ] Create `raw_youtube_metadata` and `raw_transcripts` tables in Snowflake `RAW` schema
- [ ] Implement MERGE logic in ingestion script (avoid duplicates)
- [ ] Load POC data (5 episodes) to verify schema

### 2.2 Data Format (Method B: Structured Columns)
- [ ] Verify table constraints and foreign keys between metadata and transcripts

---

## 🔄 STAGE 3: DATA TRANSFORMATION (Week 2-3)

### 3.1 Transformation Tool (Method A: dbt)
- [ ] Initialize dbt project `dbt_podcastiq`
- [ ] Configure `profiles.yml` for Snowflake
- [ ] Create Curated Layer models: `curated_episodes.sql`

### 3.2 Chunking Strategy (Method A/D: Fixed Time Window + Overlap)
- [ ] Implement `curated_segments.sql` in dbt
- [ ] Logic: 60-second windows with 15-second overlap
- [ ] Generate YouTube deep links (`?t=Xs`) in the SQL model
- [ ] Run transformation on POC data and verify chunk boundaries

---

## 🧠 STAGE 4: SEMANTIC ENRICHMENT (Week 3)

### 4.1 Embedding Generation (Method A: Snowflake Cortex)
- [ ] Create `embeddings.sql` incremental dbt model
- [ ] Use `SNOWFLAKE.CORTEX.EMBED_TEXT_768`
- [ ] Monitor credit usage on POC batch (300 segments)
- [ ] Run full batch (18,000+ segments)

### 4.2 Vector Search (Method A: Cortex Search Service)
- [ ] Create `podcast_search` service in Snowflake
- [ ] Test hybrid search quality via SQL: `CORTEX_SEARCH(...)`

### 4.3 Enrichment (Method A: Cortex COMPLETE)
- [ ] Create `topics_entities.sql` model
- [ ] Implement summarization model in `semantic.episode_summaries`

---

## 🤖 STAGE 5: MULTI-AGENT SYSTEM (Week 4-6)

### 5.1 Orchestration (Method A: LangGraph)
- [ ] Define `PodcastIQState` and workflow graph
- [ ] Implement Router Agent (routing to search vs meta queries)
- [ ] Implement Search Agent (context retrieval + adjacent segment fetch)
- [ ] Implement Summarization Agent (generating answers with refs)

### 5.2 Backend (Method A: Snowflake Cortex - llama3.1-405b)
- [ ] Configure Python client to call Cortex LLM functions

### 5.3 MCP Integration (Method A: Filesystem + Search)
- [ ] Set up MCP servers (Week 6)
- [ ] Integrate MCP tools into LangGraph workflow

---

## 🖥️ STAGE 7: USER INTERFACE (Week 5)

### 7.1 UI Framework (Method A: Streamlit)
- [ ] Build search bar and result card components
- [ ] Implement sidebar filters (Topic, Channel, Date)
- [ ] Add "Click to Play" YouTube links
- [ ] Implement "Context Expansion" to show surrounding transcript segments

---

## 🗓️ STAGE 8: ORCHESTRATION & SCHEDULING (Week 7)

### 8.1 Pipeline Orchestration (Method A: Airflow/Astro CLI)
- [ ] Move ingestion script to `youtube_extract_dag.py`
- [ ] Create `dbt_transform_dag.py` to run models post-ingestion
- [ ] Set up alerting for DAG failures

---

## 🧪 STAGE 9: TESTING & OBSERVABILITY (Week 7)

### 9.1 Data Quality (Method A: dbt Tests)
- [ ] Add `not_null` and `unique` tests to episodes and segments
- [ ] Create custom test for embedding coverage

### 9.2 Observation (Method C: Snowflake Query History)
- [ ] Create credit usage dashboard in Snowflake UI

---

## 🚀 STAGE 10: DEPLOYMENT (Week 8)

### 10.1 Strategy (Method D: Local Demo)
- [ ] Prepare demo script with 5 key queries
- [ ] Record backup video
- [ ] Finalize documentation and repository cleanup

---

## 📝 Current Focus: Week 1
**Goal:** Environment Setup & 5-Episode POC

**Blockers:** None

**Notes:** Team agreed to use one primary Snowflake account for the shared data pipeline to avoid sync issues.
