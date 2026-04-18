# PodcastIQ - AI-Powered Podcast Intelligence Platform

**Making podcast content as searchable, analyzable, and verifiable as text on the web**

PodcastIQ is an intelligent podcast discovery and analysis platform that uses semantic search, a multi-agent AI system, knowledge graph reasoning, temporal claim analysis, and hybrid fact-checking to unlock insights buried in audio content.

[![Project Status](https://img.shields.io/badge/status-complete-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## Course Information

| Field | Details |
|-------|---------|
| **Course Title** | Data Engineering: Impact of Generative AI with LLM's |
| **Course Number** | 7374-03 |
| **Term** | Spring 2026 |
| **Credit Hours** | 4 |
| **CRN** | 39499 |
| **Format** | Onsite with Virtual Components |
| **Instructor** | Kishore Aradhya — k.aradhya@northeastern.edu |

## Team

| Name |
|------|
| Aadarsh Ravi |
| Dhanvardini Rajendran |
| Priyanka Mangrulkar |

---

## The Problem

Over 5 million podcasts exist with thousands of hours of valuable content, but:
- **Audio is unsearchable** — You can't Ctrl+F through a 2-hour conversation
- **Discovery is broken** — Finding specific discussions requires listening to entire episodes
- **Claims go unverified** — Experts make predictions and assertions with no accountability over time
- **Insights are buried** — Valuable knowledge remains inaccessible in audio format

## Our Solution

PodcastIQ transforms podcast discovery with:
- **Semantic Search** — Find discussions by concept, not just keywords
- **Timestamp Precision** — Jump directly to the exact moment a topic is discussed
- **AI Summarization** — Get concise summaries without watching full episodes
- **Cross-Podcast Analysis** — Compare how different experts discuss the same topic
- **Knowledge Graph Reasoning** — Explore connections between speakers, topics, and claims
- **Temporal Claim Tracking** — See how expert opinions have evolved or been contradicted over time
- **Hybrid Fact-Checking** — Verify claims using Snowflake Cortex LLM + Brave Search web evidence
- **Intelligent Recommendations** — Discover related episodes based on content similarity

---

## Key Features

### Semantic Search
Search 290+ podcast episodes using natural language queries against 13,807 embedded chunks.

### 9-Agent AI System
1. **Router Agent** — Classifies query intent and routes to the right specialist (llama3.1-8b)
2. **Search Agent** — Cortex Search hybrid retrieval (top-8 chunks with YouTube timestamps)
3. **Summarization Agent** — Synthesizes multi-source answers with citations (llama3.1-70b)
4. **Topic Extraction Agent** — Identifies entities, people, and technologies discussed
5. **Comparison Agent** — Contrasts perspectives between speakers on a topic
6. **Recommendation Agent** — Suggests episodes by guest, channel, or topic similarity
7. **Insight Agent** — Meta-analysis: most debated topics, top speakers, channel drift
8. **Knowledge Graph Agent** — Natural language → Cypher → Neo4j graph queries
9. **Fact-Check Agent** — 3-stage pipeline: LLM pre-filter → Brave Search → LLM verdict

### Temporal Knowledge Graph
- 8,660 claims extracted and attributed to speakers across 2,317 chunks
- 243 claim evolution pairs detected (REVISED / ESCALATED / SOFTENED / CONTRADICTED / CONFIRMED)
- Drift detection shows how expert opinions have changed over time

### Neo4j Knowledge Graph
- 10,610 nodes (Channels, Episodes, Persons, Topics, Claims)
- 27,807 relationships
- GraphRAG: graph context enriches vector search results

### Input Guardrails
- Query length validation (3–500 chars)
- Prompt injection detection
- Scope classification (medical/legal/financial)
- Non-English script rejection
- Real-person disclaimer on every response

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  YouTube Transcripts (290+ episodes, 25 channels)           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Extraction & Loading (Python scripts)                      │
│  ├── channel_extraction.py (YouTube Transcript API)         │
│  ├── snowflake_loader.py (RAW → STAGING → CURATED)          │
│  └── time_stratified_extraction.py (date-balanced corpus)  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Snowflake (4-Layer Data Warehouse)                         │
│  ├── RAW: Unprocessed YouTube transcripts                   │
│  ├── STAGING: Cleaned + structured (22 flat columns)        │
│  ├── CURATED: 120s windowed chunks with YouTube deep links  │
│  └── SEMANTIC: Embeddings, topics, entities, claims         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Snowflake Cortex AI                                        │
│  ├── llama3.1-8b (Router intent classification)             │
│  ├── llama3.1-70b (Summarization, fact-checking, synthesis) │
│  ├── snowflake-arctic-embed-m (768-dim chunk embeddings)    │
│  └── Cortex Search (Hybrid vector + keyword retrieval)      │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Intelligence Layer                                         │
│  ├── Neo4j Knowledge Graph (10,610 nodes, 27,807 edges)     │
│  ├── Claim Extraction + Speaker Attribution                 │
│  ├── Temporal Analysis (claim drift detection)              │
│  └── Brave Search API (fact-checking web evidence)          │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Multi-Agent System (9 agents)                    │
│  Router → Search / Summarize / Compare / Recommend /        │
│           Insight / Temporal / Graph / FactCheck            │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Streamlit Web UI                                           │
│  ├── Chat interface (9-agent routing)                       │
│  ├── Knowledge Graph Explorer (interactive Neo4j view)      │
│  └── Channel Dashboard (credibility + topic coverage)       │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Warehouse** | Snowflake | Storage, compute, vector search |
| **LLM / Embeddings** | Snowflake Cortex | llama3.1-8b/70b, arctic-embed-m (768-dim) |
| **Knowledge Graph** | Neo4j Community (Docker) | Graph storage, GraphRAG, Cypher queries |
| **Agent Framework** | LangGraph 0.2.28 | Multi-agent orchestration |
| **Fact-Checking** | Brave Search API | Web evidence for uncertain claims |
| **Frontend** | Streamlit 1.38.0 | Interactive web UI |
| **Data Source** | YouTube Transcript API | Free podcast transcripts |
| **Transformation** | DBT 1.8.0 | SQL-based data modeling |

---

## Dataset

**290+ podcast episodes** from 25 channels across 6 categories:

- **Tech / AI:** Lex Fridman, Fireship, ThePrimeagen, a16z Podcast
- **Business:** Tim Ferriss, My First Million, Diary of a CEO, How I Built This
- **Startups:** Y Combinator, All-In Podcast, Indie Hackers
- **Science:** Huberman Lab, Peter Attia
- **General:** Joe Rogan (tech episodes)
- **More:** Additional channels covering AI, engineering, and entrepreneurship

**Statistics:**
- 290+ episodes indexed, time-stratified across 2022–2024
- 13,807 searchable chunks (120-second windows)
- 13,807 vector embeddings — 100% coverage
- 8,660 claims extracted across 2,317 chunks
- 243 temporal evolution pairs detected
- 10,610 Neo4j nodes | 27,807 relationships

---

## Getting Started

### Prerequisites

- Python 3.9+
- Snowflake account
- Docker Desktop (for Neo4j)
- Brave Search API key (free tier: 2,000 queries/month)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Aadarsh-Ravi31/PodcastIQ.git
cd PodcastIQ
```

2. **Create virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create `.env` in project root:
```bash
SNOWFLAKE_ACCOUNT=your_account.snowflakecomputing.com
SNOWFLAKE_USER=your_email@university.edu
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=LOADING_WH
SNOWFLAKE_DATABASE=PODCASTIQ
BRAVE_SEARCH_API_KEY=your_brave_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password
```

5. **Start Neo4j (Docker)**
```bash
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:community

# Neo4j Browser: http://localhost:7474
```

6. **Set up Snowflake schemas**
```sql
CREATE DATABASE PODCASTIQ;
CREATE SCHEMA PODCASTIQ.RAW;
CREATE SCHEMA PODCASTIQ.STAGING;
CREATE SCHEMA PODCASTIQ.CURATED;
CREATE SCHEMA PODCASTIQ.SEMANTIC;
CREATE SCHEMA PODCASTIQ.APP;

CREATE WAREHOUSE LOADING_WH  WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60;
CREATE WAREHOUSE TRANSFORM_WH WAREHOUSE_SIZE = 'SMALL'   AUTO_SUSPEND = 300;
CREATE WAREHOUSE SEARCH_WH   WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60;
```

7. **Run data pipeline**
```bash
# Extract transcripts
python scripts/channel_extraction.py

# Load to Snowflake
python scripts/snowflake_loader.py

# Generate chunks, embeddings, topics, entities
# (Run DBT models)
cd dbt_podcastiq && dbt run && dbt test

# Extract claims + participants
python scripts/claim_extractor.py
python scripts/guest_extractor.py

# Build Neo4j graph
python scripts/neo4j_loader.py

# Run temporal analysis
python scripts/temporal_analyzer.py --max-topics 300

# Fact-check claims
python scripts/fact_checker.py --stage1-only
```

8. **Launch Streamlit app**
```bash
cd streamlit_app
streamlit run app.py
# http://localhost:8501
```

---

## Usage

### Chat Interface

Open `http://localhost:8501` and ask natural language questions:

| Query Type | Example |
|-----------|---------|
| Search | `"What did Sam Altman say about AGI timelines?"` |
| Summarize | `"What are the best strategies for building a startup?"` |
| Compare | `"Compare Sam Altman vs Elon Musk on AI safety"` |
| Recommend | `"What should I watch about startups?"` |
| Fact-Check | `"Fact check: GPT-5 was released in 2024"` |
| Temporal | `"How has opinion on AGI changed over time?"` |
| Graph | `"Who discussed AI safety?"` |
| Insight | `"What are the most debated topics?"` |

### Knowledge Graph Explorer

Navigate to the **Graph Explorer** page to:
- Query the Neo4j graph interactively
- Explore speaker-topic-claim connections
- View episode participants and relationships

### Channel Dashboard

Navigate to the **Channel Dashboard** page to:
- View per-channel fact-check accuracy
- Explore topic coverage heatmaps
- Browse guest networks per channel

---

## Project Structure

```
PodcastIQ/
├── PRD.md                          # Product Requirements Document
├── planning.md                     # Technical implementation plan
├── tasks.md                        # Weekly task breakdown
├── requirements.txt
├── .env                            # Environment variables (git-ignored)
├── docs/                           # Generated docs, diagrams, reports
│   ├── demo_queries.md
│   ├── architecture_diagram.html
│   ├── evaluation_report.html
│   └── ...
├── scripts/                        # Data pipeline scripts
│   ├── channel_extraction.py
│   ├── snowflake_loader.py
│   ├── time_stratified_extraction.py
│   ├── claim_extractor.py
│   ├── guest_extractor.py
│   ├── neo4j_loader.py
│   ├── temporal_analyzer.py
│   ├── fact_checker.py
│   └── evaluation/                 # Evaluation suite
│       ├── router_eval.py
│       ├── retrieval_eval.py
│       ├── generation_eval.py
│       ├── latency_eval.py
│       ├── cost_eval.py
│       ├── domain_kpis.py
│       └── run_all.py
├── dbt_podcastiq/                  # DBT project
│   ├── models/
│   │   ├── staging/
│   │   ├── curated/
│   │   └── semantic/
│   └── dbt_project.yml
├── langgraph_agents/               # Multi-agent system
│   ├── agents/
│   │   ├── router.py
│   │   ├── search.py
│   │   ├── summarization.py
│   │   ├── comparison.py
│   │   ├── recommendation.py
│   │   ├── insight.py
│   │   ├── temporal.py
│   │   ├── knowledge_graph.py
│   │   └── fact_check.py
│   ├── snowflake_client.py
│   ├── state.py
│   └── graph.py
├── streamlit_app/                  # Streamlit frontend
│   ├── app.py
│   ├── components/
│   │   ├── guardrails.py
│   │   └── gpt4o_validator.py
│   └── pages/
│       ├── 1_Graph_Explorer.py
│       └── 3_Channel_Dashboard.py
└── sql/                            # Snowflake SQL scripts
    ├── schema_setup.sql
    ├── cortex_search_setup.sql
    └── ddl/
```

---

## Performance Metrics

| Metric | Target | Achieved |
|--------|--------|---------|
| Episodes Indexed | 290+ | 290+ |
| Searchable Chunks | 20,000+ | 13,807 |
| Embedding Coverage | 100% | 100% |
| Claims Extracted | 5,000+ | 8,660 |
| Claim Evolution Pairs | 200+ | 243 |
| Neo4j Nodes | 3,000+ | 10,610 |
| Neo4j Edges | 10,000+ | 27,807 |
| Agents Functional | 9 | 9/9 |
| Search Latency (p95) | < 5 seconds | < 5 seconds |

---

## Evaluation

Run the full evaluation suite:
```bash
python scripts/evaluation/run_all.py

# Quick mode (fewer queries)
python scripts/evaluation/run_all.py --quick
```

Evaluation covers:
- **Router accuracy** — 48 test queries across 8 intent types
- **Retrieval quality** — Precision@1/3/8 + MRR (LLM-as-judge)
- **Generation quality** — ROUGE-1/2/L, BERTScore F1, faithfulness/groundedness
- **Latency** — End-to-end timing per agent type (mean + p95)
- **Cost** — Token budget × Cortex pricing per agent
- **Domain KPIs** — Corpus coverage, embedding completeness, YouTube URL validity

---

## Documentation

- [PRD.md](PRD.md) — Product Requirements Document
- [planning.md](planning.md) — Detailed technical implementation plan
- [tasks.md](tasks.md) — Weekly task breakdown and progress tracking
- [docs/demo_queries.md](docs/demo_queries.md) — Confirmed working demo queries

---



## Acknowledgments

- **Snowflake Cortex AI** — Managed LLM inference and vector embeddings
- **LangGraph** — Multi-agent orchestration framework
- **Neo4j** — Graph database for knowledge graph and GraphRAG
- **Brave Search** — Web evidence API for hybrid fact-checking
- **DBT** — SQL-based data transformation
- **Streamlit** — Rapid web UI development
- **YouTube Transcript API** — Free transcript extraction

---

## Contact

| Name | Role |
|------|------|
| Aadarsh Ravi | Developer |
| Dhanvardini Rajendran | Developer |
| Priyanka Mangrulkar | Developer |

---

**Built for DAMG 7374-03 — Spring 2026 — Northeastern University**
