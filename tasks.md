# PodcastIQ - Detailed Implementation Tasks (Expanded)

**Project Timeline:** 11 Weeks (February - April 2026)
**Last Updated:** March 18, 2026
**Target Scope:** 290+ Episodes | 20,000+ Segments | Knowledge Graph | Temporal Claims | Fact-Checking

---

## 📅 Roadmap Overview

| Week | Focus | Status |
|------|-------|--------|
| 1 | Environment Setup + Steps 1-2 (Extract & Profile) | ✅ Completed |
| 2 | Steps 3-6 (Stage, Load, Clean, Structure) | ✅ Completed |
| 3 | Steps 7-8 (Chunk & Enrich) + Step 9 (Index) | ✅ Completed |
| 4 | Re-Extraction + LangGraph MVP + Claim Extraction | 🔄 In Progress |
| 5 | Neo4j Knowledge Graph + Graph Agent | ⬜ Not Started |
| 6 | Temporal Analysis + Claim Evolution | ⬜ Not Started |
| 7 | Hybrid Fact-Checking + MCP + Remaining Agents | ⬜ Not Started |
| 8 | Streamlit UI (search, graph explorer, timeline, dashboard) | ⬜ Not Started |
| 9 | Airflow Orchestration + Integration Testing | ⬜ Not Started |
| 10 | Testing, Optimization, Documentation | ⬜ Not Started |
| 11 | Final Demo + Presentation | ⬜ Not Started |

---

## THE COMPLETE PIPELINE (Expanded)

```
STEPS 1-9: DATA ENGINEERING PIPELINE (Complete ✅)

EXTRACT → PROFILE → STAGE → LOAD → CLEAN → STRUCTURE → CHUNK → ENRICH → INDEX

STEPS 10+: INTELLIGENCE LAYER (New)

STEP 10         STEP 11           STEP 12          STEP 13
RE-EXTRACT      CLAIM             KNOWLEDGE        TEMPORAL
(Python)        EXTRACTION        GRAPH            ANALYSIS

Time-stratified → Cortex LLM    → Neo4j nodes   → Claim linking
6 channels       extracts claims   & edges         Drift detection
~40 new eps      + speaker attr   Entity resol.    Evolution types
→ Fix date gaps  → SEM_CLAIMS    → GRAPH DB       → SEM_CLAIM_EVOLUTION

STEP 14         STEP 15           STEP 16          STEP 17
FACT-CHECK      AGENTS           UI                ORCHESTRATE
(Cortex + MCP)  (LangGraph)      (Streamlit)      (Airflow)

LLM pre-filter → 9 specialized  → Search UI      → Automated DAGs
+ MCP web srch   agents           Graph explorer    Daily extraction
Verification     GraphRAG          Claim timeline    Weekly fact-check
→ VERIFIED/etc  → QUERYABLE      → USER-FACING    → PRODUCTION
```

---

## 🛠️ STAGE 0: PROJECT SETUP & INFRASTRUCTURE — Week 1 ✅

### 0.1 Repository Structure
- [x] Create project root at `D:\Projects\PodcastIQ\`
- [x] Initialize Git repository
- [x] Create core directories
- [x] Create base documentation: `PRD.md`, `planning.md`, `tasks.md`, `claude.md`, `README.md`

### 0.2 Environment & Dependencies
- [x] Create virtual environment
- [x] Install dependencies

### 0.3 Snowflake Infrastructure
- [x] Create database `PODCASTIQ` with 6 schemas
- [x] Create warehouses: LOADING_WH, TRANSFORM_WH, SEARCH_WH
- [x] Set auto-suspend policies

---

## 📥 STEP 1: EXTRACT — Week 1 ✅

- [x] Finalize 25 channels across 6 genres
- [x] Create `scripts/channel_extraction.py`
- [x] Extract 250+ episodes → JSON files in `data/raw/`

---

## 📊 STEP 2: PROFILE — Week 1-2 ✅

- [x] Create `scripts/advanced_profile.py` (ydata-profiling)
- [x] Generate HTML profiling reports

---

## ☁️ STEP 3: STAGE — Week 2 ✅

- [x] PUT local JSON files to `@PODCASTIQ.RAW.PODCAST_DATA_STAGE`

---

## 📦 STEP 4: LOAD — Week 2 ✅

- [x] COPY INTO `RAW.EPISODES` + MERGE INTO `RAW.CHANNELS`

---

## 🧹 STEP 5: CLEAN — Week 2 ✅

- [x] `STAGING.STG_EPISODES` — VARIANT → 22 flat columns
- [x] `STAGING.STG_SEGMENTS` — LATERAL FLATTEN + noise removal

---

## 🔗 STEP 6: STRUCTURE — Week 2 ✅

- [x] `STAGING.INT_EPISODES` — Join with channels, add quality metrics
- [x] `STAGING.INT_SEGMENTS` — Add YouTube timestamp URLs, word counts

---

## ✂️ STEP 7: CHUNK — Week 3 ✅

- [x] `CURATED.CUR_CHUNKS` — 120-second windowed chunks with YouTube deep links

---

## 🧠 STEP 8: ENRICH — Week 3 ✅

- [x] `SEM_CHUNK_EMBEDDINGS` — VECTOR(FLOAT, 768) via arctic-embed-m
- [x] `SEM_CHUNK_TOPICS` — LLM topic extraction
- [x] `SEM_CHUNK_ENTITIES` — NER (people, orgs, tech)
- [x] `SEM_EPISODE_SUMMARIES` — Episode-level summaries

---

## 🔍 STEP 9: INDEX — Week 3-4 ✅

- [x] `PODCASTIQ_SEARCH` Cortex Search service live (since Feb 21)

---

## ✅ STEP 10: VALIDATE — Week 4

### 10.1 Data Quality Tests (dbt tests)
- [ ] `not_null` on critical columns (video_id, chunk_text, embedding)
- [ ] `unique` on primary keys (video_id, chunk_id)
- [ ] `relationships` (chunks → episodes, embeddings → chunks)
- [ ] Custom: embedding coverage = 100%
- [ ] Custom: YouTube links valid format
- [ ] Custom: timestamps chronologically ordered per episode
- [ ] Run full `dbt test` — all must pass

---

## 🔄 STEP 11: TIME-STRATIFIED RE-EXTRACTION — Week 4

### 11.1 Modify Extraction Script
- [x] Create `scripts/time_stratified_extraction.py`
- [x] Add year-range filtering: `publishedAfter` / `publishedBefore` per calendar year
- [x] Sort by viewCount within each year (top 2-3 per year)

### 11.2 Priority 1 Channels (Must Fix)
- [x] All-In Podcast: +3 from 2022, +3 from 2023, +2 from 2024 (8/8 ✅)
- [x] a16z Podcast: +2 from 2022, +3 from 2023, +3 from 2024 (8/8 ✅)
- [x] Joe Rogan: +2 from 2024 only (2022-2023 unavailable — Spotify exclusivity period)

### 11.3 Priority 2 Channels (High Value)
- [x] My First Million: +2 per year (2022-2024) (6/6 ✅)
- [x] Diary of a CEO: +2 per year (2022-2024) (6/6 ✅)
- [x] Huberman Lab: +2 per year (2022-2024) (6/6 ✅)

**Total added: 36 new episodes in ~3 minutes (Mar 18, 2026)**

### 11.4 Run Through Existing Pipeline
- [x] Run extraction (3 minutes — all channels done)
- [x] Run `snowflake_loader.py` — 286 episodes loaded, 0 errors (Mar 18, 2026)
- [ ] Verify STAGING views auto-include new data
- [x] Re-run CUR_CHUNKS for new episodes — 2,097 new chunks (Mar 18, 2026)
- [x] Run embedding generation on new chunks — 2,097 embeddings (9 sec)
- [x] Run topic/entity extraction on new chunks — 2,097 topics + entities
- [x] Verify Cortex Search auto-refreshes (auto-refreshes from SEM_CHUNK_EMBEDDINGS)
- [ ] Re-run date spread query — confirm all 6 channels now span 20+ months

### 11.5 New Semantic Tables DDL (Week 4 additions)
- [x] `sql/ddl/semantic/sem_episode_participants.sql` — created
- [x] `sql/ddl/semantic/sem_claims.sql` — created
- [x] `sql/ddl/semantic/sem_claim_evolution.sql` — created
- [x] Run DDL in Snowflake to create tables (Mar 18, 2026)
- [x] `sql/pipeline_refresh.sql` — created + executed (scripts/run_pipeline_refresh.py)

---

## 🤖 MULTI-AGENT SYSTEM — Week 4

### MVP Agent Framework
- [ ] Define `PodcastIQState` TypedDict:
  ```python
  class PodcastIQState(TypedDict):
      user_query: str
      query_type: str  # SEARCH / GRAPH / TEMPORAL / FACT_CHECK / etc.
      search_results: List[dict]
      graph_results: List[dict]
      claims: List[dict]
      summary: str
      messages: List[str]
  ```
- [ ] Create LangGraph StateGraph in `langgraph_agents/graph.py`
- [ ] Set entry point → Router Agent

### Router Agent (`langgraph_agents/agents/router.py`)
- [ ] Classify query intent using Cortex LLM
- [ ] Route to: SEARCH / GRAPH_QUERY / TEMPORAL / FACT_CHECK / SUMMARIZE / COMPARE / RECOMMEND / INSIGHT
- [ ] Handle conversational context

### Search Agent (`langgraph_agents/agents/search.py`)
- [ ] Connect to Snowflake via `snowflake-connector-python`
- [ ] Query `PODCASTIQ_SEARCH` Cortex Search service
- [ ] Return top-K chunks with YouTube links + relevance scores
- [ ] Handle empty results gracefully

### Summarization Agent (`langgraph_agents/agents/summarization.py`)
- [ ] Combine top search results into context
- [ ] Generate 2-3 sentence summary via Cortex LLM
- [ ] Append YouTube timestamp links
- [ ] (Later: include claim verification status in summaries)

### Test End-to-End
- [ ] User query → Router → Search → Summary
- [ ] Test queries:
  - "How do I optimize database performance?"
  - "Explain how large language models work"
  - "What are best practices for API design?"

---

## 📋 CLAIM EXTRACTION PIPELINE — Week 4

### Guest/Host Extraction (Tier 1 Speaker Attribution)
- [ ] Create `scripts/guest_extractor.py`
- [ ] Build regex patterns per channel for title parsing
- [ ] Hardcode known hosts per channel (Lex, Huberman, All-In crew, etc.)
- [ ] LLM fallback for tricky titles
- [ ] Create `SEM_EPISODE_PARTICIPANTS` table
- [ ] Populate for all 290+ episodes
- [ ] Verify coverage: target 70-80% of episodes with named guest

### Claim Extraction (+ Tier 2 Speaker Inference)
- [ ] Create `scripts/claim_extractor.py`
- [ ] Design claim extraction prompt:
  ```
  This chunk is from "{episode_title}" on {channel_name}.
  Participants: Host: {host_name}, Guest: {guest_name}
  
  Extract all factual claims, predictions, and strong opinions.
  For each claim, provide:
  - text: the claim statement
  - speaker: inferred speaker (use context clues)
  - attribution_confidence: HIGH / MEDIUM / LOW / UNKNOWN
  - topic: main topic
  - type: VERIFIABLE_FACT / PREDICTION / OPINION / STATISTICAL
  - sentiment: positive / negative / neutral
  
  Return as JSON array.
  ```
- [ ] Create `SEM_CLAIMS` table in Snowflake
- [ ] Run claim extraction on all chunks (batch via Cortex COMPLETE)
- [ ] Parse LLM JSON output → INSERT INTO SEM_CLAIMS
- [ ] Quality check: sample 50 claims, verify accuracy
- [ ] Log extraction stats: claims per episode, type distribution, confidence distribution

---

## 🕸️ NEO4J KNOWLEDGE GRAPH — Week 5

### Neo4j Setup
- [ ] Install Docker Desktop (if not already)
- [ ] Pull Neo4j Community Edition image: `docker pull neo4j:community`
- [ ] Start container with persistent volume
- [ ] Access Neo4j Browser at `localhost:7474`
- [ ] Complete Cypher tutorial (2-3 hours): https://neo4j.com/graphacademy/

### Graph Data Model
- [ ] Create constraints (unique IDs for all node types):
  ```cypher
  CREATE CONSTRAINT FOR (p:Person) REQUIRE p.name IS UNIQUE;
  CREATE CONSTRAINT FOR (o:Organization) REQUIRE o.name IS UNIQUE;
  CREATE CONSTRAINT FOR (t:Topic) REQUIRE t.name IS UNIQUE;
  CREATE CONSTRAINT FOR (e:Episode) REQUIRE e.video_id IS UNIQUE;
  CREATE CONSTRAINT FOR (c:Channel) REQUIRE c.channel_id IS UNIQUE;
  CREATE CONSTRAINT FOR (cl:Claim) REQUIRE cl.claim_id IS UNIQUE;
  ```

### Graph Loader
- [ ] Create `scripts/neo4j_loader.py`
- [ ] Load Channel nodes from RAW.CHANNELS
- [ ] Load Episode nodes from CUR_CHUNKS (distinct episodes)
- [ ] Load Person nodes from SEM_EPISODE_PARTICIPANTS
- [ ] Create APPEARED_ON edges (Person → Episode)
- [ ] Create BELONGS_TO edges (Episode → Channel)
- [ ] Load Claim nodes from SEM_CLAIMS
- [ ] Create MADE_CLAIM / LIKELY_MADE_CLAIM edges based on attribution_confidence
- [ ] Create DISCUSSED_IN edges for UNKNOWN speaker claims
- [ ] Create ABOUT edges (Claim → Topic)
- [ ] Create SOURCED_FROM edges (Claim → Episode)

### Entity Resolution
- [ ] Fuzzy match person names (e.g., "Sam Altman" vs "Altman" vs "Samuel Altman")
- [ ] Fuzzy match organization names (e.g., "OpenAI" vs "Open AI")
- [ ] Merge duplicate nodes, preserve aliases
- [ ] Use `thefuzz` or similar library for fuzzy matching

### Knowledge Graph Agent
- [ ] Create `langgraph_agents/agents/knowledge_graph.py`
- [ ] Connect to Neo4j via `neo4j` Python driver
- [ ] Translate natural language → Cypher queries (via Cortex LLM)
- [ ] Handle common query patterns:
  - "Who has discussed {topic}?" → MATCH (p)-[:MADE_CLAIM]->(c)-[:ABOUT]->(t {name: topic})
  - "Show {person}'s network" → MATCH (p {name})-[*1..2]-(connected) RETURN
  - "What topics does {channel} cover most?" → MATCH (e)-[:BELONGS_TO]->(ch), (c)-[:SOURCED_FROM]->(e), (c)-[:ABOUT]->(t) GROUP BY t
- [ ] Add to LangGraph graph with Router edge
- [ ] Test queries:
  - "Who has discussed AI safety?"
  - "Show Sam Altman's network across podcasts"
  - "What topics does Lex Fridman cover most?"

---

## ⏳ TEMPORAL ANALYSIS — Week 6

### Claim Linking
- [ ] Build claim similarity matching:
  - Same speaker + same topic + different dates → candidate pair
  - Same topic + different speakers + different dates → discourse evolution
- [ ] Use embedding similarity on claim text to find related claims
- [ ] Filter: minimum time delta (>30 days) to avoid same-episode duplication

### Drift Detection
- [ ] Create `SEM_CLAIM_EVOLUTION` table
- [ ] For each candidate pair, classify evolution type via Cortex LLM:
  ```
  Original claim ({date1}): "{claim1}"
  Later claim ({date2}): "{claim2}"
  
  Classify the evolution: REVISED / ESCALATED / SOFTENED / CONTRADICTED / CONFIRMED
  Explain briefly.
  ```
- [ ] Store results with drift_type, same_speaker flag, time_delta_days

### Add Evolution Edges to Neo4j
- [ ] Create EVOLVED_FROM edges between linked claims
- [ ] Include drift_type as edge property

### Temporal Analysis Agent
- [ ] Create `langgraph_agents/agents/temporal.py`
- [ ] Handle queries:
  - "How has opinion on {topic} changed over time?"
  - "Show me revised predictions from 2023"
  - "Who changed their mind about {topic}?"
  - "What claims from 2022 are now contradicted?"
- [ ] Return chronological claim sequences with drift labels
- [ ] Add to LangGraph graph
- [ ] Test with known evolution topics:
  - AGI timeline predictions (2022 vs 2025)
  - AI safety discourse shift
  - Startup valuation sentiments

---

## ✓ HYBRID FACT-CHECKING + REMAINING AGENTS — Week 7

### MCP Web Search Setup
- [ ] Sign up for Brave Search API (free tier: 2,000 queries/month)
- [ ] Install MCP SDK: `npm install -g @modelcontextprotocol/server-brave-search`
- [ ] Configure API key in environment
- [ ] Test MCP server: verify search results return

### Fact-Check Agent
- [ ] Create `langgraph_agents/agents/fact_check.py`
- [ ] Stage 1: Cortex LLM pre-filter
  - Filter claims: only VERIFIABLE_FACT and STATISTICAL types
  - Prompt: "Based on your knowledge, is this claim true, false, or uncertain?"
  - Mark confident results immediately
- [ ] Stage 2: MCP Web Search for uncertain claims
  - Formulate search query from claim text
  - Call MCP Web Search server
  - Retrieve top 3 results
- [ ] Stage 3: LLM verdict synthesis
  - Cortex LLM reads web results + original claim
  - Assign status: VERIFIED / OUTDATED / DISPUTED / UNVERIFIED / FALSE
  - Generate evidence_summary + evidence_urls
- [ ] Store results: UPDATE SEM_CLAIMS + update Neo4j Claim nodes

### Batch Fact-Checking
- [ ] Create `scripts/fact_checker.py`
- [ ] Run Stage 1 on all VERIFIABLE_FACT + STATISTICAL claims
- [ ] Run Stage 2 on uncertain claims (budget: ~500-800 web searches)
- [ ] Log verification stats: % verified, % outdated, % by channel

### Comparison Agent
- [ ] Create `langgraph_agents/agents/comparison.py`
- [ ] Use Neo4j graph edges for cross-podcast analysis
- [ ] Handle: "Compare {person1} and {person2} on {topic}"
- [ ] Output: common themes, unique perspectives, contradictions

### Recommendation Agent
- [ ] Create `langgraph_agents/agents/recommendation.py`
- [ ] Graph-based: suggest related episodes via shared topics/people
- [ ] Handle: "What else should I watch?" based on current search

### Insight Agent
- [ ] Create `langgraph_agents/agents/insight.py`
- [ ] Meta-analysis queries:
  - "Which channels have highest fact-check accuracy?"
  - "What are the most debated topics?"
  - "Give me a credibility report for {channel}"
- [ ] Calculate per-channel verification stats from SEM_CLAIMS

### Wire All Agents to Router
- [ ] Update Router Agent with all 9 routing targets
- [ ] Test full agent routing end-to-end

---

## 🖥️ STREAMLIT UI — Week 8

### Search Interface
- [ ] Search bar with placeholder "Search 290+ podcast episodes..."
- [ ] Result cards: episode title, channel, segment text, timestamp, relevance score
- [ ] Verification badges on results: ✅ Verified, ⚠️ Outdated, ❌ False, ❓ Unverified
- [ ] "Click to Play" YouTube timestamp links
- [ ] Sidebar filters: Channel, Topic, Date Range, Verification Status

### Knowledge Graph Explorer
- [ ] Interactive force-directed graph (neovis.js or react-force-graph via Streamlit component)
- [ ] Click node → show details + related claims
- [ ] Filter graph by topic, person, channel
- [ ] Highlight claim verification status with color coding

### Claim Timeline View
- [ ] Horizontal timeline showing claim evolution for a topic
- [ ] Color-coded drift types (green = confirmed, orange = revised, red = contradicted)
- [ ] Click claim → YouTube deep link to exact moment
- [ ] Show speaker attribution with confidence level

### Channel Credibility Dashboard
- [ ] Per-channel fact-check accuracy (% verified, % outdated, % false)
- [ ] Topic coverage heatmap per channel
- [ ] Guest network visualization per channel
- [ ] Episode count + date range per channel

### Episode Detail Page
- [ ] Episode summary (from SEM_EPISODE_SUMMARIES)
- [ ] List of extracted claims with verification badges
- [ ] Participants list (host + guests)
- [ ] Related episodes (via graph-based recommendation)

### User Interaction Logging
- [ ] Log searches to `APP.SEARCH_HISTORY`
- [ ] Show recent search history in sidebar

---

## 🗓️ AIRFLOW ORCHESTRATION — Week 9

### DAG 1: `youtube_extract_dag.py` (Daily at 2 AM)
- [ ] Task 1: Run extraction for new videos (all 25 channels)
- [ ] Task 2: Run `snowflake_loader.py` (incremental load)
- [ ] Task 3: Refresh CUR_CHUNKS for new episodes
- [ ] Task 4: Trigger embedding generation for new chunks
- [ ] Error handling: retry 3x with exponential backoff

### DAG 2: `claim_extraction_dag.py` (Daily, after DAG 1)
- [ ] Task 1: Run claim extraction on new chunks
- [ ] Task 2: Run guest extraction on new episodes
- [ ] Task 3: Load new claims + entities → Neo4j
- [ ] Task 4: Run claim linking for new claims
- [ ] Dependency: triggered after DAG 1 completes

### DAG 3: `fact_check_dag.py` (Weekly on Sundays)
- [ ] Task 1: Re-verify all VERIFIABLE_FACT claims (catch newly outdated)
- [ ] Task 2: Verify any new claims from past week
- [ ] Task 3: Update SEM_CLAIMS + Neo4j with new statuses
- [ ] Budget guard: cap at 500 web searches per run

### Alerting
- [ ] Email notification on DAG failure
- [ ] Slack webhook (optional)

---

## 🧪 TESTING & OPTIMIZATION — Week 10

### Data Quality (dbt tests / SQL)
- [ ] not_null on all critical columns
- [ ] unique on all primary keys
- [ ] relationships (chunks → episodes, claims → chunks, embeddings → chunks)
- [ ] Custom: embedding coverage = 100%
- [ ] Custom: all YouTube links valid format
- [ ] Custom: claim extraction coverage (% of chunks with claims)

### Graph Quality
- [ ] No orphan Person nodes (everyone appears in at least one episode)
- [ ] No orphan Claim nodes (every claim links to episode + topic)
- [ ] Entity resolution completeness (spot-check for duplicates)
- [ ] Claim evolution edge count (verify meaningful evolution detected)

### Performance
- [ ] Search latency < 5 seconds (95th percentile)
- [ ] Graph queries < 3 seconds
- [ ] Streamlit page load < 2 seconds
- [ ] Add Neo4j indexes on frequently queried properties
- [ ] Snowflake clustering keys if >10K rows
- [ ] Streamlit caching: `@st.cache_data` on all Snowflake/Neo4j queries

### Documentation
- [ ] README.md with architecture diagram
- [ ] Setup instructions (Snowflake, Neo4j, Python, Airflow)
- [ ] API documentation for agent system
- [ ] Credit usage report

---

## 🚀 FINAL DEMO & PRESENTATION — Week 11

### Demo Preparation
- [ ] Prepare demo script with 7 showcase queries
- [ ] Rehearse live demo (practice transitions, handle errors gracefully)
- [ ] Record backup demo video (in case live demo fails)
- [ ] Prepare to answer questions:
  - "Why Neo4j + Snowflake instead of just one?"
  - "How accurate is the claim extraction?"
  - "How does GraphRAG compare to vanilla RAG?"
  - "How would you scale to 1 million episodes?"
  - "What was the hardest technical challenge?"

### Slide Deck
- [ ] Problem statement (audio content is unsearchable)
- [ ] Solution overview (architecture diagram)
- [ ] Data pipeline (10-step journey — use existing diagram)
- [ ] Novel features:
  - GraphRAG (vector + graph hybrid retrieval)
  - Temporal knowledge graph (claim evolution)
  - Hybrid fact-checking (Cortex + MCP)
  - Two-tier speaker attribution
- [ ] Live demo (7 queries)
- [ ] Challenges and learnings
- [ ] Future enhancements

### Final Report (8-12 pages)
- [ ] Architecture decisions and trade-offs
- [ ] Data pipeline design (Steps 1-9)
- [ ] Intelligence layer design (Steps 10-17)
- [ ] GraphRAG implementation
- [ ] Temporal claim analysis methodology
- [ ] Fact-checking pipeline design
- [ ] Results and evaluation
- [ ] Snowflake credit usage breakdown
- [ ] Learnings and future work

### GitHub Repository
- [ ] Clean commit history
- [ ] All sensitive files in `.gitignore`
- [ ] Requirements.txt up to date
- [ ] Code comments on complex logic
- [ ] Type hints in Python code

---

## 📊 Progress Tracking

| Week | Status | Start Date | End Date | Notes |
|------|--------|------------|----------|-------|
| 1 | ✅ Completed | Feb 15 | Feb 20 | Steps 1-2: 250+ episodes extracted |
| 2 | ✅ Completed | — | Mar 17 | Steps 3-6: RAW loaded, stg/int views |
| 3 | ✅ Completed | Mar 17 | Mar 17 | Steps 7-9: Chunks, embeddings, search live |
| 4 | 🔄 In Progress | Mar 18 | — | Re-extraction + MVP agents + claim extraction |
| 5 | ⬜ Not Started | — | — | Neo4j knowledge graph |
| 6 | ⬜ Not Started | — | — | Temporal analysis + claim evolution |
| 7 | ⬜ Not Started | — | — | Fact-checking + MCP + remaining agents |
| 8 | ⬜ Not Started | — | — | Streamlit UI |
| 9 | ⬜ Not Started | — | — | Airflow orchestration |
| 10 | ⬜ Not Started | — | — | Testing + optimization + docs |
| 11 | ⬜ Not Started | — | — | Final demo + presentation |

---

## 🎯 Success Metrics

| Metric | Target |
|--------|--------|
| Episodes Indexed | 290+ |
| Searchable Chunks | 20,000+ |
| Embedding Coverage | 100% |
| Search Latency (p95) | < 5 seconds |
| Claims Extracted | 5,000+ |
| Claim Evolution Pairs | 200+ |
| Claims Fact-Checked | 500+ |
| Neo4j Nodes | 3,000+ |
| Neo4j Edges | 10,000+ |
| Agents Functional | 9 |
| Snowflake Credits Used | < 400 |
| Channels with 12+ month span | 20+ |

---

## 📝 Current Focus: Week 4

**Priority order:**
1. Time-stratified re-extraction for 6 channels (~40 new episodes)
2. Run new episodes through existing pipeline
3. LangGraph MVP: Router + Search + Summarization agents
4. Guest/host extraction (Tier 1 speaker attribution)
5. Claim extraction pipeline (+ Tier 2 speaker inference)
6. dbt validation tests (Step 10)

**Blockers:** None

**Estimated Snowflake credits this week:** ~30-40 (re-extraction enrichment + claim extraction LLM calls)