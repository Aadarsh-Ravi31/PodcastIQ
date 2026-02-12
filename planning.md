# PodcastIQ Implementation Plan

## Context

**Problem:** Over 5 million podcasts exist, but audio content is unsearchable. Users waste hours listening to entire episodes to find specific discussions, and valuable insights remain buried in audio format.

**Solution:** PodcastIQ - An AI-powered podcast discovery platform that makes podcast content as searchable as text on the web using semantic search, multi-agent orchestration, and RAG architecture.

**Why This Change:** This project addresses a real pain point while demonstrating mastery of Gen AI data engineering: ETL pipelines (Airflow, DBT), data warehousing (Snowflake), RAG implementation (Cortex Search), and Agentic AI patterns (LangGraph).

**Course Requirements Met:**
1. ✅ Data Engineering: ETL/ELT pipeline extracting YouTube transcripts → transforming with DBT → loading to Snowflake
2. ✅ Generative AI: Multi-agent system with 6 specialized agents using Snowflake Cortex LLMs
3. ✅ RAG Implementation: Vector embeddings + semantic search + context retrieval
4. ✅ Agentic AI Architecture: LangGraph orchestrating Router, Search, Summarization, Topic Extraction, Comparison, and Recommendation agents
5. ✅ MCP Integration: LangGraph agents consume MCP servers for enhanced capabilities (filesystem access, web search, etc.)

---

## High-Level Architecture

```
YouTube Transcripts (100 episodes from 10 channels)
          ↓
   Apache Airflow (ETL Orchestration)
          ↓
   Snowflake (4-Layer Data Warehouse)
   ├── RAW: Unprocessed transcripts
   ├── CURATED: Cleaned + chunked segments (60s windows)
   ├── SEMANTIC: Vector embeddings + topics
   └── APP: User interactions + search history
          ↓
   DBT (Data Transformation)
          ↓
   Snowflake Cortex AI
   ├── Embeddings: snowflake-arctic-embed-m (768-dim)
   ├── LLM: llama3.1-405b
   └── Cortex Search: Managed hybrid search
          ↓
   LangGraph Multi-Agent System
   ├── Router Agent (orchestration)
   ├── Search Agent (Cortex Search queries)
   ├── Summarization Agent (episode summaries)
   ├── Topic Extraction Agent (NER, entities)
   ├── Comparison Agent (cross-podcast analysis)
   └── Recommendation Agent (personalized suggestions)
          ↑
   MCP Servers (External Tool Integration)
   ├── Filesystem MCP (read transcripts, logs)
   ├── Web Search MCP (real-time fact-checking)
   └── Database MCP (query Snowflake directly)
          ↓
   Streamlit UI (Search + Results + Deep Links)
```

**Data Flow:**
1. Airflow extracts YouTube transcripts daily → loads to Snowflake RAW
2. DBT transforms RAW → CURATED (chunking) → SEMANTIC (embeddings)
3. LangGraph agents query Snowflake Cortex Search → generate responses
4. Streamlit displays results with clickable YouTube timestamp links

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Data Warehouse | Snowflake | Storage, compute, vector search |
| LLM/AI | Snowflake Cortex | llama3.1-405b for reasoning, Arctic Embed for embeddings |
| Orchestration | Apache Airflow (local via Astro CLI) | ETL automation, scheduling |
| Transformation | DBT | SQL-based data modeling |
| Agent Framework | LangGraph | Multi-agent state machines |
| Frontend | Streamlit | Interactive chat interface |
| Data Source | YouTube Transcript API | Free podcast transcripts (no API key) |

**Cost:** $0 - Leverages university Snowflake access + free YouTube transcripts

---

## Snowflake Schema Design

### Layer 1: RAW (Landing Zone)
**Tables:**
- `raw.raw_youtube_metadata` - Video titles, channels, durations, publish dates
- `raw.raw_transcripts` - Individual transcript lines with timestamps

### Layer 2: CURATED (Cleaned & Chunked)
**Tables:**
- `curated.curated_episodes` - Full episodes with cleaned transcripts
- `curated.curated_segments` - **60-second chunks with 15-second overlap** (critical for search quality)

**Chunking Strategy:** Time-based windowing ensures consistent chunk sizes (~200-400 words) and preserves timestamp accuracy for deep linking to YouTube.

### Layer 3: SEMANTIC (AI-Enhanced)
**Tables:**
- `semantic.embeddings` - 768-dimensional vectors (arctic-embed-m) for semantic search
- `semantic.topics_entities` - Extracted people, organizations, technologies via Cortex LLM
- `semantic.episode_summaries` - Multi-level summaries (1-sentence, paragraph, detailed)

**Cortex Search Service:** Managed hybrid search combining vector similarity + keyword matching + LLM re-ranking.

### Layer 4: APP (User Interactions)
**Tables:**
- `app.search_history` - Query logs and clicked results
- `app.user_preferences` - Saved episodes and favorite topics
- `app.recommendation_scores` - Pre-computed personalized rankings

**Estimated Storage:** <100MB for 100 episodes (well within free tier)

---

## ETL Pipeline Design

### Airflow DAGs

**DAG 1: `youtube_extract_dag.py`** (Daily at 2 AM)
```
Task 1: Fetch new video IDs from target channels (YouTube Data API)
Task 2: Extract transcripts using youtube-transcript-api
Task 3: Validate transcript quality (>100 words, English only)
Task 4: Load to Snowflake RAW layer (incremental MERGE)
Task 5: Trigger DBT transformation
```

**Key Features:**
- Retry logic: 3 attempts with exponential backoff (5 min → 15 min → 30 min)
- Error handling: Failed videos logged to separate table for manual review
- Incremental loading: Only new transcripts, no duplicates

**DAG 2: `dbt_transform_dag.py`** (Triggered after ingestion)
```
Task 1: Run curated models (clean transcripts → chunk into segments)
Task 2: Run semantic models (generate embeddings → extract topics)
Task 3: Run DBT tests (data quality checks)
```

**DAG 3: `embedding_generation_dag.py`** (Weekly on Sundays)
```
Task 1: Generate embeddings for any segments missing them
Task 2: Refresh Cortex Search index
```

---

## DBT Transformation Strategy

### Critical DBT Models

**1. `curated_segments.sql`** (Materialized as Table)
- Implements chunking: 60-second windows with 15-second overlap
- Uses window functions: `FLOOR(start_seconds / 45)` creates overlapping groups
- Generates YouTube deep links: `'https://youtu.be/' || video_id || '?t=' || start_seconds || 's'`
- Links segments: Adds `previous_segment_id` and `next_segment_id` for context retrieval

**2. `embeddings.sql`** (Incremental Materialization)
- Generates embeddings: `SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', text)`
- Incremental: Only processes new segments (reduces Cortex API costs)
- Output: 768-dimensional vectors stored in VECTOR column type

**3. `topics_entities.sql`** (Incremental)
- Uses Cortex LLM for NER: `SNOWFLAKE.CORTEX.COMPLETE('llama3.1-405b', extraction_prompt)`
- Extracts: People, organizations, technologies, topics
- Stores confidence scores for filtering

**DBT Best Practices:**
- Incremental models for expensive operations (embeddings, LLM calls)
- Materialized tables for frequently queried data (episodes, segments)
- Data quality tests: Not null checks, referential integrity, embedding coverage

---

## RAG Implementation

### Cortex Search Configuration

**Decision:** Use Snowflake Cortex Search (managed service) instead of custom vector search.

**Rationale:**
- ✅ Hybrid search built-in (vector + keyword + re-ranking)
- ✅ Auto-refreshing index (2-minute lag configurable)
- ✅ Production-ready without manual index management
- ✅ Simpler implementation (critical for 8-week timeline)

**Setup:**
```sql
CREATE CORTEX SEARCH SERVICE podcast_search
ON embedding_vector
WAREHOUSE = SEARCH_WH
TARGET_LAG = '2 minutes'
AS (
    SELECT
        e.segment_id,
        s.text AS segment_text,
        e.embedding_vector,
        s.youtube_timestamp_link,
        s.episode_id,
        ep.channel_name,
        ep.episode_title
    FROM semantic.embeddings e
    JOIN curated.curated_segments s ON e.segment_id = s.segment_id
    JOIN curated.curated_episodes ep ON s.episode_id = ep.episode_id
);
```

### Search Query Pattern

**Hybrid Search (Recommended):**
```sql
SELECT * FROM TABLE(
    CORTEX_SEARCH(
        'podcast_search',
        'How do I optimize database queries?',  -- User query
        {'limit': 10, 'search_mode': 'hybrid'}  -- Vector + keyword + rerank
    )
)
ORDER BY SEARCH_SCORE DESC;
```

**Context Retrieval Strategy:**
For each top result, fetch adjacent segments using `previous_segment_id` and `next_segment_id` to provide richer context to LLM (improves answer quality).

---

## Multi-Agent Architecture

### Agent Priority

**MVP Agents (Weeks 3-4):**
1. **Router Agent** - Analyzes user query → routes to appropriate specialist
2. **Search Agent** - Queries Cortex Search → retrieves relevant segments
3. **Summarization Agent** - Generates concise summaries with YouTube links

**Stretch Agents (Weeks 5-6):**
4. **Topic Extraction Agent** - NER and entity analysis
5. **Comparison Agent** - Cross-podcast perspective analysis
6. **Recommendation Agent** - Personalized episode suggestions

### LangGraph Workflow

```python
# State schema
class PodcastIQState(TypedDict):
    user_query: str
    query_type: str  # 'search', 'summarize', 'compare'
    search_results: List[dict]
    summary: str
    messages: List[str]

# Build graph
workflow = StateGraph(PodcastIQState)
workflow.add_node("router", router_agent)
workflow.add_node("search_agent", search_agent)
workflow.add_node("summarization_agent", summarization_agent)

workflow.set_entry_point("router")
workflow.add_conditional_edges("router", route_to_agent)
workflow.add_edge("search_agent", "summarization_agent")
workflow.add_edge("summarization_agent", END)

app = workflow.compile()
```

### Agent Implementations

**Router Agent:**
- Uses Claude/Llama to classify query intent
- Returns routing decision: "SEARCH", "SUMMARIZE", "COMPARE", etc.

**Search Agent:**
- Executes Snowflake Cortex Search query
- Returns top 5-10 segments with relevance scores
- Retrieves adjacent segments for context

**Summarization Agent:**
- Combines top search results
- Uses Cortex LLM to generate 2-3 sentence summary
- Appends YouTube timestamp links

---

## 8-Week Implementation Plan

### Week 1: Environment Setup & Proof of Concept
**Goal:** Extract 5-10 episodes, load to Snowflake, verify pipeline works

**Tasks:**
- Set up Snowflake account, create databases/schemas (RAW, CURATED, SEMANTIC, APP)
- Install Airflow locally (Astro CLI recommended)
- Create Python environment with youtube-transcript-api, snowflake-connector-python
- Write simple script to extract 5 transcripts (hardcoded video IDs)
- Manually load transcripts to Snowflake RAW layer

**Deliverable for Professor:**
- Demo live Snowflake query showing 5 episodes loaded
- Screenshot of Snowflake UI with data

**Time Allocation:** 2 days setup, 3 days testing, 2 days buffer

---

### Week 2: Full ETL Pipeline (100 Episodes)
**Goal:** Automate extraction of 100 episodes from 10 channels (~10 episodes per channel)

**Tasks:**
- Finalize channel list (10 tech/AI podcasts with English transcripts) - **Present to user for approval before finalizing**
- Build `youtube_extract_dag.py` with error handling
- Implement incremental loading (MERGE statement)
- Create DBT project structure
- Write `curated_episodes.sql` model
- Run DBT to transform RAW → CURATED

**Deliverable for Professor:**
- Airflow UI screenshot showing successful DAG run
- SQL query: `SELECT COUNT(*) FROM curated.curated_episodes` (target: 100+)
- CSV export of loaded episodes with channel distribution

**Candidate Podcasts (to be confirmed with user):**
- Tech/AI: Lex Fridman, All-In Podcast, Fireship, ThePrimeagen
- Business: Tim Ferriss, How I Built This, My First Million
- Startups: Y Combinator, Indie Hackers
- Science: Huberman Lab, Peter Attia
- General: Joe Rogan clips (tech episodes only)

**Channel Selection Process:**
1. Present candidate list to user for approval
2. Validate each channel has English transcripts available
3. Test extraction with 1-2 episodes per channel
4. Finalize list of 10 channels before full extraction

**Risk Mitigation:** If <30 episodes loaded due to missing transcripts, manually curate additional videos with confirmed captions.

---

### Week 3: Chunking & Embeddings
**Goal:** Generate searchable segments with vector embeddings

**Tasks:**
- Implement `curated_segments.sql` with 60s/15s overlap chunking
- Verify chunking: Check avg segments per episode (~60)
- Write `embeddings.sql` using Cortex EMBED_TEXT_768
- Run full embedding generation (estimated 6,000 segments × 768 dims)
- Create Cortex Search service
- Test basic semantic search query

**Deliverable for Professor:**
- Demo Cortex Search query: "Show me segments about Kubernetes scaling"
- Return top 5 results with YouTube timestamp links
- Screenshot showing embedding coverage: `SELECT COUNT(*) FROM semantic.embeddings`

**Performance Target:**
- Embedding generation: <3 hours on SMALL warehouse
- Search query latency: <2 seconds

---

### Week 4: Multi-Agent MVP (Router + Search + Summarization)
**Goal:** Build core LangGraph system with 3 agents

**Tasks:**
- Set up LangGraph project structure
- Implement Router Agent using Claude Sonnet or Llama
- Implement Search Agent (Cortex Search integration)
- Implement Summarization Agent (Cortex LLM)
- Test end-to-end workflow: User query → Router → Search → Summary
- Add YouTube timestamp links to final output

**Deliverable for Professor:**
- Live demo: User types "Explain how neural networks work"
- System returns: 2-3 sentence summary + 3 timestamped YouTube links
- Agent trace showing: Router classified as "SEARCH" → Found 5 segments → Generated summary

**Test Queries:**
1. "How do I optimize database performance?"
2. "What are the best practices for API design?"
3. "Explain Rust's ownership model"

---

### Week 5: Streamlit UI + Topic Extraction
**Goal:** User-facing interface + 4th agent

**Tasks:**
- Build Streamlit app with search bar
- Display search results in cards (episode title, channel, timestamp, relevance score)
- Add click-to-YouTube functionality
- Implement Topic Extraction Agent (queries semantic.topics_entities table)
- Add topic filter sidebar (checkboxes for AI, databases, programming, etc.)

**Deliverable for Professor:**
- Deployed Streamlit app (localhost or streamlit.io free tier)
- Screenshot showing:
  - Search query entered
  - 5 result cards with topics tagged
  - Topic filter active (e.g., only show "AI" episodes)

**UI Features:**
- Search bar with placeholder "Search 100+ podcast episodes..."
- Results display: Episode title, channel name, segment text preview, timestamp link, relevance score
- Topic tags: Color-coded badges showing extracted topics
- Sidebar filters: Channel, topic, date range

---

### Week 6: Comparison & Recommendation Agents + MCP Integration
**Goal:** Complete all 6 agents + integrate MCP for enhanced capabilities

**Tasks:**
- Implement Comparison Agent (analyzes how different podcasters discuss same topic)
- Implement Recommendation Agent (content-based filtering using embeddings)
- Add "Related Episodes" section to Streamlit UI
- Create app.search_history table
- Log all user searches for analytics
- **MCP Integration:** Set up Filesystem and Web Search MCP servers
- Integrate MCP clients into LangGraph agents
- Add MCP tool routing to Router Agent

**Deliverable for Professor:**
- Demo comparison query: "Compare views on AI safety from Lex Fridman vs ThePrimeagen"
- System returns: Common themes, unique perspectives, contradictions
- Show recommendation panel suggesting 3 similar episodes based on current search

**Comparison Agent Output Format:**
```
Common Themes:
- Both discuss the importance of alignment research
- Both mention the rapid pace of AI development

Unique Perspectives:
- Lex Fridman: Emphasizes philosophical implications
- ThePrimeagen: Focuses on practical engineering trade-offs

Contradictions:
- Lex is optimistic about AGI timeline (10-20 years)
- ThePrimeagen is skeptical about near-term AGI
```

**MCP Integration Details:**

**Setup Tasks:**
1. Install MCP SDK: `npm install -g @modelcontextprotocol/sdk`
2. Set up Filesystem MCP server (read logs, transcripts, debug files)
3. Configure Web Search MCP server (Brave Search API or alternative)
4. Create Python wrappers for MCP tools as LangChain tools
5. Add MCP tool executor to LangGraph workflow
6. Update Router Agent to conditionally route to MCP tools

**MCP Use Cases:**
- **Filesystem MCP:** "Why did yesterday's Airflow DAG fail?" → Reads log file
- **Web Search MCP:** "Is the AI claim from episode 42 still accurate?" → Searches web
- **Debug Assistant:** "Show me the raw transcript for video xyz" → Accesses file system

**Success Criteria:**
- Router Agent successfully routes MCP tool requests
- Filesystem MCP can read Airflow logs (<2 seconds latency)
- Web Search MCP returns relevant real-time results
- MCP tools accessible from Streamlit UI

**Contingency:** If MCP integration takes >8 hours, make it optional/post-project enhancement. Core agents take priority.

---

### Week 7: Testing, Optimization, Documentation
**Goal:** Production readiness

**Tasks:**
- Write DBT tests (referential integrity, null checks, embedding coverage)
- Add Airflow alerting (email on DAG failure)
- Optimize Snowflake queries (add clustering keys if >10K rows)
- Implement Streamlit caching (`@st.cache_data`) to reduce query load
- Write README.md with architecture diagram
- Create user guide for Streamlit app
- Monitor Snowflake credit usage (should be <100 credits used)

**Deliverable for Professor:**
- Documentation PDF containing:
  - Architecture diagram (similar to this plan)
  - Sample SQL queries demonstrating each layer
  - Snowflake credit usage report (screenshot from `WAREHOUSE_METERING_HISTORY`)
  - Known limitations and future enhancements

**DBT Tests to Implement:**
```sql
-- Test: All segments have embeddings
-- Test: No null values in episode titles
-- Test: All YouTube links are valid format
-- Test: Segment timestamps are chronological
```

---

### Week 8: Final Demo Preparation & Presentation
**Goal:** Polished demo showcasing all features

**Tasks:**
- Prepare 10-minute demo script with 3-5 example queries
- Create slide deck:
  - Problem statement (audio content is unsearchable)
  - Solution overview (architecture diagram)
  - Technical highlights (RAG + multi-agent system)
  - Challenges and learnings
  - Future enhancements
- Record backup demo video (in case live demo fails)
- Prepare to answer questions on:
  - Why Snowflake over other data warehouses?
  - How does Cortex Search compare to Pinecone/Weaviate?
  - What was the hardest technical challenge?
  - How would you scale to 1 million episodes?

**Deliverable for Professor:**
- Live demo presentation (10 minutes)
- GitHub repository with full code and documentation
- Final report (5-10 pages) covering:
  - Architecture decisions and trade-offs
  - Data pipeline design
  - RAG implementation approach
  - Multi-agent system design
  - Learnings and future work
  - Snowflake credit usage breakdown

**Demo Script Example:**
1. **Search Query:** "How do I scale a database?" → Shows 5 results with timestamps
2. **Click Link:** Opens YouTube at exact moment (e.g., 45:23)
3. **Topic Filter:** Filter to only "Database" topics → Results update
4. **Comparison Query:** "Compare MongoDB vs PostgreSQL discussions" → Side-by-side analysis
5. **Recommendations:** Show "You might also like these episodes" panel

**Success Metrics:**
- ✅ 50+ episodes indexed
- ✅ <5 second search latency
- ✅ <$200 in Snowflake credits used
- ✅ 6 agents functional (even if simple implementations)

---

## Critical Files to Implement

### Priority 1 (Weeks 1-2): Data Pipeline
1. **airflow/dags/youtube_extract_dag.py** - Core ETL orchestration
2. **dbt_podcastiq/models/curated/curated_episodes.sql** - Episode cleaning
3. **dbt_podcastiq/models/curated/curated_segments.sql** - **Critical chunking logic**

### Priority 2 (Weeks 3-4): RAG System
4. **dbt_podcastiq/models/semantic/embeddings.sql** - Vector generation
5. **sql/cortex_search_setup.sql** - Managed search service configuration
6. **langgraph_agents/agents/search.py** - Search agent implementation

### Priority 3 (Weeks 4-5): Multi-Agent System
7. **langgraph_agents/graph.py** - LangGraph workflow orchestration
8. **langgraph_agents/agents/router.py** - Query routing logic
9. **langgraph_agents/agents/summarization.py** - Summary generation

### Priority 4 (Week 5): User Interface
10. **streamlit_app/app.py** - Main UI entry point
11. **streamlit_app/components/search_bar.py** - Search input component
12. **streamlit_app/components/results_display.py** - Results rendering

---

## Key Design Decisions

### 1. Use Snowflake Cortex Search (Managed) vs Custom Vector Search
**Decision:** Cortex Search (managed service)

**Rationale:**
- Production-ready hybrid search (vector + keyword + re-ranking) out-of-the-box
- No need to manage vector indexes manually
- Auto-refreshing with configurable 2-minute lag
- Simpler implementation critical for 8-week timeline
- Trade-off: Less control over ranking algorithm (acceptable for MVP)

---

### 2. Chunking Strategy: Time-Based vs Semantic
**Decision:** Time-based chunking (60-second windows with 15-second overlap)

**Rationale:**
- Preserves timestamp accuracy for YouTube deep linking (critical feature)
- Consistent chunk sizes (~200-400 words at typical podcast speaking rate)
- Simple to implement in DBT using window functions
- 25% overlap maintains context across chunk boundaries
- Alternative (semantic chunking based on topic shifts) rejected due to:
  - Complexity of maintaining timestamps
  - Inconsistent chunk sizes
  - Harder to debug

---

### 3. MVP Agent Prioritization
**Decision:** Focus on Router, Search, and Summarization for Weeks 3-4

**Rationale:**
- Router demonstrates orchestration (required for "agentic AI patterns")
- Search is core RAG functionality (required for project)
- Summarization adds value beyond raw search results (impresses professor)
- Comparison and Recommendation are stretch goals (Weeks 5-6)
- If behind schedule, 3 agents are sufficient for passing grade

---

### 4. Airflow Deployment: Local vs Cloud
**Decision:** Local Airflow via Astro CLI

**Rationale:**
- Zero cost (no cloud infrastructure bills)
- Full control for learning and debugging
- Sufficient for 100 episodes (not production scale)
- Easy to migrate to Astronomer cloud later if needed
- Alternative (GitHub Actions) considered but Airflow is more industry-standard

---

### 5. DBT Materialization Strategy
**Decision:** Incremental for expensive models (embeddings, LLM calls), Table for frequently queried data

**Rationale:**
- Incremental models reduce Cortex API costs (only process new segments)
- Table materialization optimizes search query performance
- Follows DBT best practices for cost-efficient transformations

---

## Development Environment Setup

### Required Accounts
1. **Snowflake** - University access (already available)
2. **GitHub** - Code repository and version control
3. **YouTube Data API** - Optional for metadata (transcripts don't require API key)
4. **Anthropic/OpenAI** - Optional for Claude/GPT agents (can use Cortex LLMs instead)

### Local Installation

**1. Python Environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**requirements.txt:**
```
youtube-transcript-api==0.6.2
snowflake-connector-python==3.12.0
apache-airflow==2.10.0
apache-airflow-providers-snowflake==5.6.0
dbt-snowflake==1.8.0
langgraph==0.2.28
langchain==0.3.0
langchain-core==0.3.0
streamlit==1.38.0
pandas==2.2.0
python-dotenv==1.0.0
mcp==0.9.0  # Model Context Protocol SDK (if available)
```

**Additional MCP Setup (Node.js required):**
```bash
# Install MCP servers globally
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-brave-search  # Optional: requires Brave API key
```

**2. Airflow Setup (Astro CLI):**
```bash
# Install Astro CLI
# Mac: brew install astro
# Windows: https://docs.astronomer.io/astro/cli/install-cli

# Initialize project
astro dev init

# Start Airflow
astro dev start  # Runs on localhost:8080
```

**3. DBT Setup:**
```bash
dbt init dbt_podcastiq

# Configure ~/.dbt/profiles.yml with Snowflake credentials
```

**4. Snowflake Configuration:**
```sql
-- Create database hierarchy
CREATE DATABASE PODCASTIQ;
CREATE SCHEMA PODCASTIQ.RAW;
CREATE SCHEMA PODCASTIQ.CURATED;
CREATE SCHEMA PODCASTIQ.SEMANTIC;
CREATE SCHEMA PODCASTIQ.APP;

-- Create warehouses (right-sized for cost optimization)
CREATE WAREHOUSE LOADING_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60  -- 1 minute idle timeout
    AUTO_RESUME = TRUE;

CREATE WAREHOUSE TRANSFORM_WH
    WAREHOUSE_SIZE = 'SMALL'
    AUTO_SUSPEND = 300  -- 5 minutes
    AUTO_RESUME = TRUE;

CREATE WAREHOUSE SEARCH_WH
    WAREHOUSE_SIZE = 'X-SMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;
```

### Project Directory Structure
```
podcastiq/
├── airflow/
│   └── dags/
│       ├── youtube_extract_dag.py
│       ├── dbt_transform_dag.py
│       └── embedding_generation_dag.py
├── dbt_podcastiq/
│   ├── models/
│   │   ├── curated/
│   │   │   ├── curated_episodes.sql
│   │   │   └── curated_segments.sql
│   │   ├── semantic/
│   │   │   ├── embeddings.sql
│   │   │   └── topics_entities.sql
│   │   └── app/
│   └── dbt_project.yml
├── langgraph_agents/
│   ├── agents/
│   │   ├── router.py
│   │   ├── search.py
│   │   └── summarization.py
│   └── graph.py
├── streamlit_app/
│   └── app.py
├── sql/
│   ├── schema_setup.sql
│   └── cortex_search_setup.sql
├── .env
├── requirements.txt
└── README.md
```

---

## Cost Management

### Snowflake Credit Budget

**Free Tier:** $400 in credits (200 credits × $2/credit)

**Projected 8-Week Usage (100 Episodes):**
| Activity | Warehouse | Credits/Hour | Total Hours | Total Credits |
|----------|-----------|--------------|-------------|---------------|
| Initial data load (100 episodes) | SMALL | 2 | 2 | 4 |
| Daily incremental loads | X-SMALL | 1 | 1.2 | 8.4 |
| DBT transformations (2x data) | SMALL | 2 | 24 | 48 |
| Embedding generation (12K segments) | SMALL | 2 | 6 | 12 |
| Search queries (testing) | X-SMALL | 1 | 10 | 10 |
| Development/exploration | X-SMALL | 1 | 45 | 45 |
| **Total Estimated** | | | | **127.4 credits** |

**Estimated Cost:** 127.4 credits × $2 = **$254.80** (well within $400 budget, 36% buffer remaining)

### Cost Optimization Strategies

1. **Aggressive Auto-Suspend:** All warehouses suspend after 60-300 seconds of inactivity
2. **Use X-SMALL Warehouses:** Sufficient for <10K rows (our dataset is ~6K segments)
3. **Query Optimization:** Use LIMIT during development, add indexes for production
4. **Result Caching:** Snowflake caches identical queries for 24 hours (free)
5. **Incremental DBT Models:** Only process new data (reduces Cortex API calls)
6. **Streamlit Caching:** Use `@st.cache_data` to avoid redundant Snowflake queries

**Weekly Monitoring Query:**
```sql
SELECT
    WAREHOUSE_NAME,
    SUM(CREDITS_USED) AS total_credits,
    SUM(CREDITS_USED) * 2 AS cost_usd
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME;
```

**Budget Alert:** Set resource monitor at 150 credits (75% of budget) to notify before overages.

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Learning curve for 4+ new technologies** | HIGH | - Focus on MVP features first<br>- Week 1 entirely for setup<br>- Use official quickstart guides<br>- Join Snowflake/DBT community Slack |
| **Transcript quality issues (auto-captions ~90% accurate)** | MEDIUM | - Pre-filter: Only use channels with clear audio<br>- Add quality_score heuristic in DBT<br>- Display disclaimer in UI |
| **Snowflake credits exceeding budget** | MEDIUM | - Monitor weekly credit usage<br>- Set resource monitor at 150 credits<br>- Use X-SMALL warehouses<br>- Cache aggressively |
| **Time constraints (8 weeks, solo)** | HIGH | - Strict MVP prioritization (3 agents in Week 4)<br>- Reduce scope to 50 episodes if needed<br>- Timebox features: >4 hours → defer to "future work" |
| **Scope creep (6 agents is ambitious)** | MEDIUM | - Week 4 checkpoint: Only 3 agents required<br>- Weeks 5-6: Add agents incrementally<br>- If behind, cut Comparison/Recommendation |
| **Missing transcripts for some videos** | LOW | - Accept 70-80% success rate as normal<br>- Target 50 episodes from 75 attempts<br>- Choose popular channels (more likely to have transcripts) |

**Contingency Plan (If Behind Schedule by Week 4):**
- Cut to 4 agents total (drop Comparison and Recommendation)
- Simplify UI to basic search box + results list (no visualizations)
- Use 30 high-quality episodes instead of 50 mediocre ones

---

## Verification Plan

### End-to-End Testing

**Week 2 Verification:**
```sql
-- Confirm 50 episodes loaded
SELECT COUNT(*) FROM curated.curated_episodes;  -- Expected: 50+

-- Check transcript quality
SELECT AVG(word_count), MIN(word_count), MAX(word_count)
FROM curated.curated_episodes;  -- Expected: 3000-5000 avg
```

**Week 3 Verification:**
```sql
-- Confirm chunking worked
SELECT COUNT(*) FROM curated.curated_segments;  -- Expected: 3000-6000

-- Verify embeddings generated
SELECT COUNT(*) FROM semantic.embeddings;  -- Should match segments count

-- Test Cortex Search
SELECT * FROM TABLE(
    CORTEX_SEARCH('podcast_search', 'machine learning', {'limit': 5})
);  -- Expected: 5 relevant results with scores >0.5
```

**Week 4 Verification:**
```python
# Test LangGraph workflow
result = app.invoke({
    "user_query": "How do neural networks work?",
    "messages": []
})

# Expected output:
# {
#   "summary": "2-3 sentence summary...",
#   "search_results": [5 segments with YouTube links],
#   "messages": ["Router: SEARCH", "Search: Found 5 segments", "Summary: Generated"]
# }
```

**Week 5 Verification:**
- Open Streamlit app at `localhost:8501`
- Type query "database optimization"
- Verify: Results display, topic tags shown, YouTube links clickable
- Click result → YouTube opens at correct timestamp

**Week 8 Final Check:**
- All 6 agents respond to test queries
- Search latency <5 seconds
- Snowflake credits used <150
- README.md complete with setup instructions
- Demo video recorded (backup)

---

## Immediate Actions After Plan Approval

Once you approve this plan, I will immediately execute the following setup tasks:

### 1. Project Structure Creation
**Location:** `D:\Projects\PodcastIQ\`

**Files to create:**
```
D:\Projects\PodcastIQ/
├── PRD.md (Product Requirements Document)
├── tasks.md (Implementation checklist with weekly breakdown)
├── claude.md (Instructions for future Claude Code sessions)
├── planning.md (This plan file, copied for reference)
├── .gitignore
├── README.md
└── (subfolders will be created in Week 1)
```

### 2. PRD.md (Product Requirements Document)
Contains:
- Project overview and objectives
- Target users and use cases
- Functional requirements (data pipeline, search, agents, UI)
- Non-functional requirements (performance, cost, scalability)
- Success criteria and KPIs
- Technical constraints

### 3. tasks.md (Implementation Checklist)
Contains:
- Week-by-week task breakdown (pulled from this plan)
- Checkbox format for tracking progress
- Dependencies between tasks
- Owner field (for future team expansion)
- Status tracking (Not Started, In Progress, Completed, Blocked)

### 4. claude.md (Session Instructions)
Contains instructions for future Claude Code sessions:
- **Always read `planning.md` at the start of every conversation** to understand project context
- **Check `tasks.md` before starting work** to see current progress and next priorities
- **Mark completed tasks immediately** in tasks.md using Edit tool
- Project-specific coding standards and conventions
- Common commands and workflows
- Links to key documentation (Snowflake, DBT, LangGraph)

### 5. Channel Selection Process
Before starting Week 2 extraction, I will:
1. Present candidate podcast channel list with sample episodes
2. Validate transcript availability for each channel
3. Get your approval on final 10 channels
4. Document channel list in PRD.md

---

## Next Steps

1. **Approve this plan** - Confirm the approach aligns with your vision
2. **I'll create project structure** - PRD, tasks.md, claude.md at `D:\Projects\PodcastIQ\`
3. **Week 1 kickoff** - Set up Snowflake environment and Airflow
4. **Proof of concept** - Extract 5-10 episodes to validate approach
5. **Weekly check-ins** - Update professor with progress and metrics

**Key Decisions Made:**
- ✅ 100 episodes total (~10 per channel)
- ✅ Snowflake Cortex LLMs only (no external API costs)
- ✅ MCP client integration (Filesystem + Web Search)
- ✅ Suggested podcast list (to be confirmed in Week 2)
- ✅ Local Airflow via Astro CLI
- ✅ Project location: `D:\Projects\PodcastIQ\`

---

## Future Enhancements (Post-Project)

**If we had more time:**
1. Speaker diarization (distinguish between host and guest)
2. Multi-language support (Spanish, French podcasts)
3. Audio clip generation (auto-generate shareable clips)
4. Chrome extension (highlight and search while watching YouTube)
5. Collaborative filtering for recommendations (requires user accounts)
6. Podcast creator analytics dashboard
7. Build custom MCP server (expose PodcastIQ search as tool for other LLM apps)
8. Real-time podcast monitoring (auto-ingest new episodes daily)
9. Transcript quality improvement (use Whisper for re-transcription)

**Startup Potential:** This could evolve into a SaaS product for podcast discovery, media companies, or educational platforms.
