# PodcastIQ - Implementation Tasks

**Project Timeline:** 8 Weeks (February - April 2026)
**Last Updated:** February 12, 2026

This file tracks all implementation tasks for the PodcastIQ project. Mark tasks as completed using `[x]` as you finish them.

---

## ✅ Week 0: Project Setup (Current Week)

### Project Structure
- [x] Create project folder at `D:\Projects\PodcastIQ\`
- [x] Create PRD.md (Product Requirements Document)
- [x] Create tasks.md (this file)
- [x] Create claude.md (session instructions)
- [x] Create planning.md (copy of approved plan)
- [x] Create .gitignore
- [x] Create README.md with project overview
- [x] Initialize Git repository
- [x] Create initial directory structure

**Status:** Completed
**Deliverable:** Project foundation ready for Week 1 development

---

## Week 1: Environment Setup & Proof of Concept

**Goal:** Extract 5-10 episodes, load to Snowflake, verify pipeline works

### Snowflake Setup
- [ ] Create Snowflake account using university credentials
- [ ] Create database: `PODCASTIQ`
- [ ] Create schemas: `RAW`, `CURATED`, `SEMANTIC`, `APP`
- [ ] Create warehouses: `LOADING_WH` (X-SMALL), `TRANSFORM_WH` (SMALL), `SEARCH_WH` (X-SMALL)
- [ ] Configure auto-suspend settings (60-300 seconds)
- [ ] Test Snowflake connection from local machine

### Python Environment
- [ ] Create virtual environment: `python -m venv venv`
- [ ] Install dependencies from `requirements.txt`
- [ ] Test youtube-transcript-api with 1 sample video
- [ ] Test snowflake-connector-python connection

### Airflow Setup
- [ ] Install Astro CLI (Mac: `brew install astro` / Windows: follow docs)
- [ ] Initialize Airflow project: `astro dev init`
- [ ] Start Airflow locally: `astro dev start`
- [ ] Access Airflow UI at `localhost:8080` (admin/admin)
- [ ] Configure Snowflake connection in Airflow UI

### Proof of Concept
- [ ] Select 5 YouTube podcast videos (tech/AI related, confirmed transcripts)
- [ ] Write simple Python script to extract transcripts
- [ ] Manually create `raw.raw_youtube_metadata` table in Snowflake
- [ ] Manually create `raw.raw_transcripts` table in Snowflake
- [ ] Load 5 episodes into Snowflake RAW layer
- [ ] Verify data with: `SELECT COUNT(*) FROM raw.raw_transcripts;`

### Deliverable for Professor
- [ ] Screenshot of Snowflake UI showing 5 episodes loaded
- [ ] SQL query showing transcript data
- [ ] Brief update email/document describing setup progress

**Status:** Not Started
**Time Allocation:** 2 days setup, 3 days testing, 2 days buffer
**Blocker(s):** None

---

## Week 2: Full ETL Pipeline (100 Episodes)

**Goal:** Automate extraction of 100 episodes from 10 channels

### Channel Selection
- [ ] Present candidate channel list to user for approval
- [ ] Validate each channel has English transcripts available
- [ ] Test extraction with 1-2 episodes per channel
- [ ] Finalize list of 10 channels
- [ ] Document approved channels in PRD.md

**Candidate Channels:**
- Tech/AI: Lex Fridman, All-In Podcast, Fireship, ThePrimeagen
- Business: Tim Ferriss, How I Built This, My First Million
- Startups: Y Combinator, Indie Hackers
- Science: Huberman Lab, Peter Attia

### Airflow DAG Development
- [ ] Create `youtube_extract_dag.py` file
- [ ] Implement Task 1: Fetch video IDs from channels (YouTube Data API)
- [ ] Implement Task 2: Extract transcripts using youtube-transcript-api
- [ ] Implement Task 3: Validate transcript quality (>100 words, English only)
- [ ] Implement Task 4: Load to Snowflake RAW layer (incremental MERGE)
- [ ] Add error handling: 3 retries with exponential backoff
- [ ] Create failed_videos logging table
- [ ] Test DAG with 10 episodes first
- [ ] Run full extraction for 100 episodes
- [ ] Schedule DAG to run daily at 2 AM

### DBT Project Setup
- [ ] Install dbt-snowflake: `pip install dbt-snowflake`
- [ ] Initialize DBT project: `dbt init dbt_podcastiq`
- [ ] Configure `~/.dbt/profiles.yml` with Snowflake credentials
- [ ] Create `dbt_podcastiq/models/curated/` folder
- [ ] Create `dbt_podcastiq/models/semantic/` folder
- [ ] Create `dbt_podcastiq/models/app/` folder

### DBT Models (Curated Layer)
- [ ] Write `curated_episodes.sql` model
- [ ] Test model: `dbt run --models curated_episodes`
- [ ] Verify output: `SELECT COUNT(*) FROM curated.curated_episodes;`
- [ ] Add DBT tests for data quality (not null, unique keys)

### DAG Integration
- [ ] Create `dbt_transform_dag.py` (triggered after ingestion)
- [ ] Add Task 1: Run curated models (`dbt run --models curated`)
- [ ] Test end-to-end: YouTube extraction → DBT transformation
- [ ] Verify 100 episodes in `curated.curated_episodes`

### Deliverable for Professor
- [ ] Airflow UI screenshot showing successful DAG run
- [ ] SQL result: `SELECT COUNT(*) FROM curated.curated_episodes;` (100+)
- [ ] CSV export of loaded episodes with channel distribution
- [ ] Brief report on any failed extractions and why

**Status:** Not Started
**Dependencies:** Week 1 setup complete
**Risk:** Transcript availability may be <70%, need buffer episodes
**Blocker(s):** None

---

## Week 3: Chunking & Embeddings

**Goal:** Generate searchable segments with vector embeddings

### Chunking Implementation (DBT)
- [ ] Write `curated_segments.sql` model
- [ ] Implement 60-second windows with 15-second overlap chunking
- [ ] Add window function: `FLOOR(start_seconds / 45)` for overlapping groups
- [ ] Generate YouTube deep links: `'https://youtu.be/' || video_id || '?t=' || start_seconds || 's'`
- [ ] Add `previous_segment_id` and `next_segment_id` for context linking
- [ ] Test chunking with 1 episode first
- [ ] Run full chunking: `dbt run --models curated_segments`
- [ ] Verify avg segments per episode (~60): `SELECT episode_id, COUNT(*) FROM curated.curated_segments GROUP BY episode_id;`
- [ ] Expected total: 6,000-12,000 segments

### Embedding Generation (DBT)
- [ ] Write `embeddings.sql` incremental model
- [ ] Use Snowflake Cortex: `SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', text)`
- [ ] Test on 100 segments first (estimate time)
- [ ] Run full embedding generation for all segments
- [ ] Monitor Snowflake warehouse usage (should take <3 hours on SMALL warehouse)
- [ ] Verify embedding coverage: `SELECT COUNT(*) FROM semantic.embeddings;`
- [ ] Ensure 100% match: embeddings count = segments count

### Cortex Search Setup
- [ ] Create SQL script: `cortex_search_setup.sql`
- [ ] Define Cortex Search service: `CREATE CORTEX SEARCH SERVICE podcast_search`
- [ ] Configure warehouse: `SEARCH_WH`
- [ ] Set target lag: 2 minutes
- [ ] Define search columns: segment_text, embedding_vector, metadata
- [ ] Execute setup script in Snowflake
- [ ] Verify service created: `SHOW CORTEX SEARCH SERVICES;`

### Search Testing
- [ ] Test basic semantic search: "Show me segments about Kubernetes scaling"
- [ ] Verify top 5 results returned with relevance scores
- [ ] Check YouTube timestamp links are correct format
- [ ] Test search latency: aim for <2 seconds
- [ ] Test different query types (technical, conceptual, broad, specific)

### Deliverable for Professor
- [ ] Demo Cortex Search query with top 5 results
- [ ] Screenshot showing embedding count matches segment count
- [ ] Report on search latency and relevance quality
- [ ] Sample results showing YouTube deep links

**Status:** Not Started
**Dependencies:** Week 2 complete (100 episodes in curated layer)
**Performance Target:** Embedding generation <3 hours, search latency <2 seconds
**Blocker(s):** None

---

## Week 4: Multi-Agent MVP (Router + Search + Summarization)

**Goal:** Build core LangGraph system with 3 agents

### LangGraph Project Setup
- [ ] Create folder: `langgraph_agents/`
- [ ] Create subfolder: `langgraph_agents/agents/`
- [ ] Install LangGraph: `pip install langgraph langchain langchain-core`
- [ ] Create `state.py` - Define `PodcastIQState` TypedDict
- [ ] Create `graph.py` - Main workflow definition

### Router Agent (Agent 1)
- [ ] Create `agents/router.py`
- [ ] Define `router_agent(state)` function
- [ ] Implement query intent classification (SEARCH, SUMMARIZE, COMPARE, etc.)
- [ ] Use Snowflake Cortex `llama3.1-405b` for classification
- [ ] Define `route_to_agent(state)` conditional edge function
- [ ] Test router with 5 sample queries
- [ ] Verify correct routing to next agent

### Search Agent (Agent 2)
- [ ] Create `agents/search.py`
- [ ] Define `search_agent(state)` function
- [ ] Integrate Snowflake Cortex Search API
- [ ] Execute hybrid search query
- [ ] Return top 5-10 segments with metadata
- [ ] Implement context retrieval (fetch adjacent segments)
- [ ] Test search with various queries
- [ ] Verify relevance scores and timestamp links

### Summarization Agent (Agent 3)
- [ ] Create `agents/summarization.py`
- [ ] Define `summarization_agent(state)` function
- [ ] Combine top 3 search results as context
- [ ] Use Snowflake Cortex `llama3.1-405b` to generate 2-3 sentence summary
- [ ] Append YouTube timestamp links to summary
- [ ] Test summary quality with 5 queries
- [ ] Ensure summaries are concise and accurate

### LangGraph Workflow Assembly
- [ ] In `graph.py`, create `StateGraph(PodcastIQState)`
- [ ] Add nodes: router, search_agent, summarization_agent
- [ ] Set entry point: `workflow.set_entry_point("router")`
- [ ] Add conditional edge: router → search_agent (based on query type)
- [ ] Add edge: search_agent → summarization_agent
- [ ] Add edge: summarization_agent → END
- [ ] Compile graph: `app = workflow.compile()`
- [ ] Test end-to-end: User query → Router → Search → Summary

### Integration Testing
- [ ] Test Query 1: "How do I optimize database performance?"
- [ ] Test Query 2: "What are the best practices for API design?"
- [ ] Test Query 3: "Explain Rust's ownership model"
- [ ] Verify agent trace shows correct routing
- [ ] Verify summaries include 2-3 YouTube links
- [ ] Check total response time <10 seconds

### Deliverable for Professor
- [ ] Live demo: "Explain how neural networks work" → Returns summary + 3 links
- [ ] Agent trace screenshot showing: Router → Search → Summarization
- [ ] Document with sample queries and outputs
- [ ] Code walkthrough explaining LangGraph architecture

**Status:** Not Started
**Dependencies:** Week 3 complete (Cortex Search operational)
**Test Queries:** 3 technical queries across different topics
**Blocker(s):** None

---

## Week 5: Streamlit UI + Topic Extraction

**Goal:** User-facing interface + 4th agent

### Streamlit App Setup
- [ ] Create folder: `streamlit_app/`
- [ ] Create `app.py` main entry point
- [ ] Create `components/` subfolder
- [ ] Install Streamlit: `pip install streamlit plotly`
- [ ] Test basic Streamlit app: `streamlit run app.py`
- [ ] Verify app opens at `localhost:8501`

### Search Interface Components
- [ ] Create `components/search_bar.py`
- [ ] Add search input: `st.text_input("Search 100+ podcast episodes...")`
- [ ] Add "Search" button
- [ ] Connect button to LangGraph agent invocation
- [ ] Display loading spinner during search

### Results Display Components
- [ ] Create `components/results_display.py`
- [ ] Implement card-based layout for results
- [ ] Display per result: Episode title, channel, segment text preview (150 chars)
- [ ] Add timestamp link (opens YouTube in new tab at exact moment)
- [ ] Show relevance score (0-1, as progress bar)
- [ ] Add "Show more context" expander (displays adjacent segments)
- [ ] Implement pagination if >10 results

### Topic Extraction Agent (Agent 4)
- [ ] Create `agents/topic_extraction.py`
- [ ] Define `topic_extraction_agent(state)` function
- [ ] Query `semantic.topics_entities` table for top entities
- [ ] Group by entity_type (PERSON, ORG, TOPIC, TECHNOLOGY)
- [ ] Return top 10 topics with frequency counts
- [ ] Display topics as color-coded badges in UI
- [ ] Add to LangGraph workflow (optional parallel execution)

### Filters & Sidebar
- [ ] Add sidebar with `st.sidebar`
- [ ] Implement channel filter (checkboxes for 10 channels)
- [ ] Implement topic filter (checkboxes for top 10 topics)
- [ ] Add date range slider (if publish dates available)
- [ ] Add "Clear all filters" button
- [ ] Re-run search with filters applied

### Streamlit Caching
- [ ] Add `@st.cache_data` to search function
- [ ] Cache Snowflake connection: `@st.cache_resource`
- [ ] Set TTL to 1 hour for search results
- [ ] Test cache hit (search same query twice, verify faster second time)

### Deliverable for Professor
- [ ] Deployed Streamlit app (localhost or streamlit.io)
- [ ] Screenshot showing: Search query → 5 result cards → Topic tags
- [ ] Demo video showing filtering by channel and topic
- [ ] User guide document explaining UI features

**Status:** Not Started
**Dependencies:** Week 4 complete (3 agents functional)
**UI Target:** Clean, intuitive interface with <2 second page load
**Blocker(s):** None

---

## Week 6: Comparison & Recommendation Agents + MCP Integration

**Goal:** Complete all 6 agents + integrate MCP for enhanced capabilities

### Comparison Agent (Agent 5)
- [ ] Create `agents/comparison.py`
- [ ] Define `comparison_agent(state)` function
- [ ] Group search results by channel
- [ ] Use Snowflake Cortex LLM to analyze perspectives
- [ ] Generate comparison: Common themes, unique perspectives, contradictions
- [ ] Format output as JSON with sections
- [ ] Add to LangGraph workflow
- [ ] Test query: "Compare views on AI safety from Lex Fridman vs ThePrimeagen"

### Recommendation Agent (Agent 6)
- [ ] Create `agents/recommendation.py`
- [ ] Define `recommendation_agent(state)` function
- [ ] Implement content-based filtering using embeddings
- [ ] Query similar episodes using vector cosine similarity
- [ ] Return top 5 related episodes
- [ ] Add to LangGraph workflow
- [ ] Display "Related Episodes" section in Streamlit UI

### App Layer Schema
- [ ] Create `app.search_history` table in Snowflake
- [ ] Log all user queries with timestamp and results
- [ ] Create `app.user_preferences` table (optional for now)
- [ ] Track clicked results for analytics

### MCP Integration Setup
- [ ] Install Node.js (v16+ required for MCP servers)
- [ ] Install MCP SDK: `npm install -g @modelcontextprotocol/sdk`
- [ ] Install Filesystem MCP: `npm install -g @modelcontextprotocol/server-filesystem`
- [ ] Install Brave Search MCP: `npm install -g @modelcontextprotocol/server-brave-search` (optional)
- [ ] Install Python MCP client: `pip install mcp` (if available)

### Filesystem MCP Integration
- [ ] Start Filesystem MCP server locally
- [ ] Create Python wrapper for MCP Filesystem tool as LangChain tool
- [ ] Define `read_file_via_mcp(filepath)` function
- [ ] Test reading Airflow log file: `/var/log/airflow/dag_errors.log`
- [ ] Add MCP tools to LangGraph ToolExecutor
- [ ] Update Router Agent to route "debug" queries to Filesystem MCP

### Web Search MCP Integration
- [ ] Start Brave Search MCP server (or alternative)
- [ ] Create Python wrapper for MCP Web Search tool
- [ ] Define `web_search_via_mcp(query)` function
- [ ] Test query: "Latest AI regulation news 2026"
- [ ] Add to Router Agent routing logic (keywords: "current", "latest", "recent")

### MCP Tool Routing Logic
- [ ] Update `router_agent()` to detect MCP-relevant queries
- [ ] If query contains "debug" or "log" → use Filesystem MCP
- [ ] If query contains "current" or "latest" → use Web Search MCP
- [ ] Otherwise → use standard podcast search flow
- [ ] Ensure graceful fallback if MCP unavailable

### Integration Testing
- [ ] Test MCP Query 1: "Why did yesterday's Airflow DAG fail?"
- [ ] Test MCP Query 2: "Is the quantum computing claim from episode 42 still accurate?"
- [ ] Test hybrid query: Standard search + MCP web fact-check
- [ ] Verify MCP tools complete in <3 seconds
- [ ] Test from Streamlit UI

### Streamlit UI Updates
- [ ] Add "Related Episodes" panel to results page
- [ ] Add "Comparison View" page for side-by-side analysis
- [ ] Display MCP tool results (if used)
- [ ] Add tabs: Search | Comparison | Recommendations

### Deliverable for Professor
- [ ] Demo comparison query showing common themes and differences
- [ ] Demo recommendation panel with 3 similar episodes
- [ ] Demo MCP query (e.g., "Why did DAG fail?") returning log file content
- [ ] Screenshot showing all 6 agents operational
- [ ] Brief report on MCP integration challenges and solutions

**Status:** Not Started
**Dependencies:** Week 5 complete (Streamlit UI + 4 agents)
**Contingency:** If MCP takes >8 hours, make optional and focus on 6 core agents
**Blocker(s):** None

---

## Week 7: Testing, Optimization, Documentation

**Goal:** Production readiness

### DBT Testing
- [ ] Write DBT test: All segments have embeddings
- [ ] Write DBT test: No null values in episode titles
- [ ] Write DBT test: All YouTube links are valid format (regex check)
- [ ] Write DBT test: Segment timestamps are chronological
- [ ] Run all tests: `dbt test`
- [ ] Fix any failing tests
- [ ] Document test coverage in README

### Airflow Monitoring & Alerting
- [ ] Configure email alerts for DAG failures (or Slack)
- [ ] Test alert by forcing DAG failure
- [ ] Verify alert received
- [ ] Add retry delay escalation (5 min → 15 min → 30 min)

### Snowflake Optimization
- [ ] Check query performance: `QUERY_HISTORY` view
- [ ] Add clustering key to `curated_segments` if >10K rows: `CLUSTER BY (episode_id, start_seconds)`
- [ ] Add indexes (if supported) for frequently filtered columns
- [ ] Run `ANALYZE TABLE` to update statistics
- [ ] Re-test search latency after optimization

### Streamlit Performance
- [ ] Implement `@st.cache_data` for all expensive functions
- [ ] Minimize Snowflake query count (batch queries where possible)
- [ ] Test app with 5 concurrent users (ask friends to test)
- [ ] Optimize page load: lazy-load non-critical components

### Credit Usage Monitoring
- [ ] Run weekly credit usage query:
```sql
SELECT WAREHOUSE_NAME, SUM(CREDITS_USED) AS total_credits, SUM(CREDITS_USED) * 2 AS cost_usd
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME;
```
- [ ] Verify total credits used <150 (target: <130)
- [ ] If approaching limit, suspend non-essential warehouses
- [ ] Screenshot credit usage for professor deliverable

### Documentation
- [ ] Write README.md with:
  - [ ] Project overview (1-2 paragraphs)
  - [ ] Architecture diagram (ASCII or image)
  - [ ] Setup instructions (how to run locally)
  - [ ] Environment variables needed (.env.example)
  - [ ] Sample queries
  - [ ] Troubleshooting guide
- [ ] Create user guide for Streamlit app:
  - [ ] How to search
  - [ ] How to use filters
  - [ ] How to interpret results
  - [ ] Example queries
- [ ] Update PRD.md with any changes made during implementation
- [ ] Update tasks.md to reflect actual completion dates

### Code Cleanup
- [ ] Add type hints to all Python functions
- [ ] Add docstrings to all functions (Google style)
- [ ] Remove commented-out code
- [ ] Fix any linting errors: `flake8` or `black`
- [ ] Ensure consistent code formatting

### Deliverable for Professor
- [ ] Documentation PDF containing:
  - [ ] Architecture diagram
  - [ ] Sample SQL queries for each Snowflake layer
  - [ ] Snowflake credit usage report (screenshot)
  - [ ] Known limitations
  - [ ] Future enhancements
- [ ] Updated README.md in GitHub repo
- [ ] All DBT tests passing
- [ ] Search latency <5 seconds consistently

**Status:** Not Started
**Dependencies:** Week 6 complete (all agents functional)
**Goal:** Polish and professionalism
**Blocker(s):** None

---

## Week 8: Final Demo Preparation & Presentation

**Goal:** Polished demo showcasing all features

### Demo Script Development
- [ ] Write 10-minute demo script with 5 example queries
- [ ] Select queries that showcase different agents:
  - [ ] Query 1: Semantic search (Search Agent)
  - [ ] Query 2: Summarization (Summarization Agent)
  - [ ] Query 3: Topic extraction (Topic Extraction Agent)
  - [ ] Query 4: Comparison (Comparison Agent)
  - [ ] Query 5: MCP tool (Filesystem or Web Search)
- [ ] Practice demo flow (dry run with timer)
- [ ] Prepare answers to anticipated questions

### Slide Deck Creation
- [ ] Slide 1: Title + Team (just you)
- [ ] Slide 2: Problem Statement (audio content unsearchable)
- [ ] Slide 3: Solution Overview (PodcastIQ high-level)
- [ ] Slide 4: Architecture Diagram (Airflow → Snowflake → DBT → LangGraph → Streamlit)
- [ ] Slide 5: Data Pipeline (ETL process, 100 episodes, 12K segments)
- [ ] Slide 6: RAG Implementation (embeddings, Cortex Search, chunking strategy)
- [ ] Slide 7: Multi-Agent System (6 agents with LangGraph)
- [ ] Slide 8: MCP Integration (Filesystem + Web Search)
- [ ] Slide 9: Demo Transition (transition to live demo)
- [ ] Slide 10: Technical Challenges (learning curve, transcript quality, cost management)
- [ ] Slide 11: Learnings (what worked, what didn't, key takeaways)
- [ ] Slide 12: Future Enhancements (speaker diarization, multi-language, etc.)
- [ ] Slide 13: Thank You + Questions

### Demo Video Recording (Backup)
- [ ] Record screen demo of all 5 queries
- [ ] Include voiceover explaining each step
- [ ] Test video playback (ensure audio/video quality)
- [ ] Upload to Google Drive or YouTube (unlisted)
- [ ] Have link ready in case live demo fails

### Question Preparation
- [ ] Why Snowflake over other data warehouses?
- [ ] How does Cortex Search compare to Pinecone/Weaviate?
- [ ] What was the hardest technical challenge?
- [ ] How would you scale to 1 million episodes?
- [ ] What would you change if you did this again?
- [ ] How accurate are the auto-generated transcripts?
- [ ] Can this be productionized for real users?

### Final Report Writing
- [ ] Section 1: Executive Summary (1 page)
- [ ] Section 2: Architecture & Design Decisions (2 pages)
- [ ] Section 3: Data Pipeline Implementation (1 page)
- [ ] Section 4: RAG System & Search Quality (1 page)
- [ ] Section 5: Multi-Agent System Design (1 page)
- [ ] Section 6: MCP Integration (1 page)
- [ ] Section 7: Challenges & Learnings (1 page)
- [ ] Section 8: Results & Metrics (1 page)
- [ ] Section 9: Future Work (0.5 page)
- [ ] Section 10: References (0.5 page)
- [ ] Appendix: Code snippets, SQL queries, screenshots
- [ ] Proofread and format (10 pages total)

### GitHub Repository Finalization
- [ ] Ensure all code is committed and pushed
- [ ] Create `.gitignore` (exclude .env, venv, __pycache__)
- [ ] Add clear README.md with setup instructions
- [ ] Add LICENSE file (MIT or Apache 2.0)
- [ ] Tag final version: `git tag v1.0.0`
- [ ] Make repository public (or share with professor)

### Final Testing
- [ ] Run end-to-end test of all 5 demo queries
- [ ] Verify YouTube links open at correct timestamps
- [ ] Test Streamlit app on fresh browser (clear cache)
- [ ] Verify DBT tests all pass: `dbt test`
- [ ] Check Snowflake credit usage (should be <150)

### Deliverable for Professor
- [ ] Live demo presentation (10 minutes)
- [ ] Slide deck (PDF + PowerPoint)
- [ ] GitHub repository URL with full code
- [ ] Final report (10 pages PDF)
- [ ] Demo video (backup, unlisted YouTube link)
- [ ] Snowflake credit usage breakdown

**Status:** Not Started
**Dependencies:** Week 7 complete (production-ready code)
**Success Criteria:** Impressive demo, all features working, clear presentation
**Blocker(s):** None

---

## Post-Project (Optional Future Work)

These tasks are **not required** for the 8-week course project but could be fun to explore afterward:

### Feature Enhancements
- [ ] Speaker diarization (host vs guest)
- [ ] Multi-language support (Spanish, French)
- [ ] Audio clip generation (shareable snippets)
- [ ] Chrome extension for YouTube search
- [ ] Collaborative filtering recommendations
- [ ] Podcast creator analytics dashboard

### Infrastructure
- [ ] Deploy to production (AWS, GCP, or Snowflake Native Apps)
- [ ] Build custom MCP server (expose PodcastIQ search as tool)
- [ ] Real-time monitoring (auto-ingest new episodes daily)
- [ ] Whisper re-transcription (improve quality from 90% to 99%)

### Community
- [ ] Open-source project (accept contributions)
- [ ] Write blog post about building PodcastIQ
- [ ] Submit to Snowflake/DBT community showcases

---

## Progress Tracking

| Week | Status | Start Date | End Date | Notes |
|------|--------|------------|----------|-------|
| 0 | Completed | Feb 12 | Feb 12 | Project setup - all files and directories created |
| 1 | Not Started | - | - | - |
| 2 | Not Started | - | - | - |
| 3 | Not Started | - | - | - |
| 4 | Not Started | - | - | - |
| 5 | Not Started | - | - | - |
| 6 | Not Started | - | - | - |
| 7 | Not Started | - | - | - |
| 8 | Not Started | - | - | - |

**Overall Progress:** 7/7 Week 0 tasks completed (100%)

---

## Notes & Blockers

**Current Focus:** Week 1 - Environment Setup & Proof of Concept

**Blockers:** None

**Questions for Professor:**
- (Add any questions as they arise)

**Lessons Learned:**
- (Document learnings as you go)

---

**Remember:**
- Check this file at the start of every coding session
- Mark tasks as complete immediately: `[ ]` → `[x]`
- Update Progress Tracking table weekly
- Document blockers and questions as they arise
