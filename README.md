# 🎙️ PodcastIQ - AI-Powered Podcast Discovery Platform

**Making podcast content as searchable as text on the web**

PodcastIQ is an intelligent podcast discovery and analysis platform that uses semantic search, multi-agent AI, and RAG (Retrieval-Augmented Generation) architecture to make audio content searchable, analyzable, and discoverable.

[![Project Status](https://img.shields.io/badge/status-in%20development-yellow)](https://github.com/yourusername/podcastiq)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## 🚀 The Problem

Over 5 million podcasts exist with thousands of hours of valuable content, but:
- **Audio is unsearchable** - You can't Ctrl+F through a 2-hour conversation
- **Discovery is broken** - Finding specific discussions requires listening to entire episodes
- **Time is wasted** - Users spend hours hoping to find relevant information
- **Insights are buried** - Valuable knowledge remains inaccessible in audio format

## 💡 Our Solution

PodcastIQ transforms podcast discovery with:
- ✅ **Semantic Search** - Find discussions by concept, not just keywords
- ✅ **Timestamp Precision** - Jump directly to the exact moment a topic is discussed
- ✅ **AI Summarization** - Get concise summaries without watching full episodes
- ✅ **Cross-Podcast Analysis** - Compare how different experts discuss the same topic
- ✅ **Intelligent Recommendations** - Discover related episodes based on your interests
- ✅ **Real-Time Context** - Fact-check claims with web search via MCP integration

---

## ✨ Key Features

### 🔍 Semantic Search
Search 100+ podcast episodes using natural language:
```
"How do neural networks work?"
"Best practices for database optimization"
"Explain Rust's ownership model"
```

### 🎯 Timestamp Deep Links
Every result includes a clickable YouTube link that opens at the exact moment:
```
https://youtu.be/VIDEO_ID?t=2743s  → Opens at 45:43
```

### 🤖 Multi-Agent AI System (6 Specialized Agents)
1. **Router Agent** - Orchestrates query routing to appropriate specialists
2. **Search Agent** - Executes semantic search across 12,000+ segments
3. **Summarization Agent** - Generates concise 2-3 sentence summaries
4. **Topic Extraction Agent** - Identifies entities, people, technologies discussed
5. **Comparison Agent** - Analyzes perspectives across multiple podcasters
6. **Recommendation Agent** - Suggests related episodes based on content similarity

### 🔧 MCP Integration
- **Filesystem MCP** - Debug Airflow logs: *"Why did yesterday's DAG fail?"*
- **Web Search MCP** - Fact-check claims: *"Is the AI claim from episode 42 still accurate?"*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  YouTube Transcripts (100 episodes from 10 channels)        │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Apache Airflow (ETL Orchestration)                         │
│  ├── youtube_extract_dag.py (Daily ingestion)               │
│  ├── dbt_transform_dag.py (Transformation)                  │
│  └── embedding_generation_dag.py (Weekly embeddings)        │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Snowflake (4-Layer Data Warehouse)                         │
│  ├── RAW: Unprocessed YouTube transcripts                   │
│  ├── CURATED: Cleaned + chunked (60s windows, 15s overlap)  │
│  ├── SEMANTIC: Vector embeddings (768-dim) + topics         │
│  └── APP: User interactions + search history                │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Snowflake Cortex AI                                        │
│  ├── llama3.1-405b (Summarization, entity extraction)       │
│  ├── snowflake-arctic-embed-m (768-dim embeddings)          │
│  └── Cortex Search (Hybrid vector + keyword search)         │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph Multi-Agent System                               │
│  ├── Router → Search → Summarization (Core workflow)        │
│  └── Topic Extraction, Comparison, Recommendation (Advanced)│
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  Streamlit Web UI                                           │
│  ├── Search bar + filters (channel, topic, date)            │
│  ├── Results cards with timestamp links                     │
│  └── Comparison view + recommendations panel                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Data Warehouse** | Snowflake | Storage, compute, vector search |
| **AI/LLM** | Snowflake Cortex | llama3.1-405b, Arctic Embed (768-dim) |
| **Orchestration** | Apache Airflow | ETL automation, scheduling |
| **Transformation** | DBT | SQL-based data modeling |
| **Agent Framework** | LangGraph | Multi-agent orchestration |
| **Frontend** | Streamlit | Interactive web UI |
| **Data Source** | YouTube Transcript API | Free podcast transcripts |
| **MCP** | Model Context Protocol | Filesystem + Web Search tools |

---

## 📊 Dataset

**100 podcast episodes** from 10 channels across 5 categories:

- **Tech/AI:** Lex Fridman, All-In Podcast, Fireship, ThePrimeagen
- **Business:** Tim Ferriss, How I Built This, My First Million
- **Startups:** Y Combinator, Indie Hackers
- **Science:** Huberman Lab, Peter Attia
- **General:** Joe Rogan (tech episodes)

**Statistics:**
- 100 episodes indexed
- 12,000+ searchable segments (60-second chunks with 15-second overlap)
- 768-dimensional vector embeddings for semantic search
- Search latency: <2 seconds average

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Node.js 16+ (for MCP servers)
- Snowflake account (free trial or university access)
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/podcastiq.git
cd podcastiq
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

4. **Install MCP servers (optional)**
```bash
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-brave-search
```

5. **Configure Snowflake credentials**

Create `.env` file in project root:
```bash
SNOWFLAKE_ACCOUNT=your_account.snowflakecomputing.com
SNOWFLAKE_USER=your_email@university.edu
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=LOADING_WH
SNOWFLAKE_DATABASE=PODCASTIQ
```

Configure DBT (`~/.dbt/profiles.yml`):
```yaml
dbt_podcastiq:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: your_account
      user: your_username
      password: your_password
      role: PODCASTIQ_DEV
      database: PODCASTIQ
      warehouse: TRANSFORM_WH
      schema: CURATED
      threads: 4
```

6. **Set up Snowflake schemas**
```sql
-- Run in Snowflake UI or snowsql
CREATE DATABASE PODCASTIQ;
CREATE SCHEMA PODCASTIQ.RAW;
CREATE SCHEMA PODCASTIQ.CURATED;
CREATE SCHEMA PODCASTIQ.SEMANTIC;
CREATE SCHEMA PODCASTIQ.APP;

CREATE WAREHOUSE LOADING_WH WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60;
CREATE WAREHOUSE TRANSFORM_WH WAREHOUSE_SIZE = 'SMALL' AUTO_SUSPEND = 300;
CREATE WAREHOUSE SEARCH_WH WAREHOUSE_SIZE = 'X-SMALL' AUTO_SUSPEND = 60;
```

7. **Start Airflow (Astro CLI)**
```bash
# Install Astro CLI first: https://docs.astronomer.io/astro/cli/install-cli

astro dev init
astro dev start

# Access Airflow UI: http://localhost:8080 (admin/admin)
```

8. **Run DBT transformations**
```bash
cd dbt_podcastiq
dbt run
dbt test
```

9. **Launch Streamlit app**
```bash
cd streamlit_app
streamlit run app.py

# Access UI: http://localhost:8501
```

---

## 💻 Usage

### Basic Search

1. Open Streamlit app at `http://localhost:8501`
2. Enter a natural language query:
   ```
   "How do I scale a database?"
   ```
3. View results with:
   - Episode title and channel
   - Relevant text segment (150-char preview)
   - YouTube timestamp link
   - Relevance score
   - Topic tags

### Advanced Queries

**Comparison:**
```
"Compare views on AI safety from Lex Fridman vs ThePrimeagen"
```

**Topic Filtering:**
- Use sidebar to filter by channel or topic (AI, databases, programming)

**MCP Debug Query:**
```
"Why did yesterday's Airflow DAG fail?"
```

---

## 📁 Project Structure

```
D:\Projects\PodcastIQ/
├── PRD.md                          # Product Requirements Document
├── planning.md                     # Technical implementation plan
├── tasks.md                        # Weekly task breakdown
├── claude.md                       # Session instructions for Claude Code
├── README.md                       # This file
├── .env                            # Environment variables (git-ignored)
├── .gitignore
├── requirements.txt
├── airflow/
│   └── dags/
│       ├── youtube_extract_dag.py
│       ├── dbt_transform_dag.py
│       └── embedding_generation_dag.py
├── dbt_podcastiq/
│   ├── models/
│   │   ├── curated/
│   │   ├── semantic/
│   │   └── app/
│   └── dbt_project.yml
├── langgraph_agents/
│   ├── agents/
│   │   ├── router.py
│   │   ├── search.py
│   │   ├── summarization.py
│   │   ├── topic_extraction.py
│   │   ├── comparison.py
│   │   └── recommendation.py
│   ├── state.py
│   └── graph.py
├── streamlit_app/
│   ├── app.py
│   └── components/
└── sql/
    ├── schema_setup.sql
    └── cortex_search_setup.sql
```

---

## 🎯 Roadmap

### ✅ Completed (Week 0-3)
- [x] Project setup and planning
- [x] ETL pipeline (100 episodes ingested)
- [x] Chunking and embeddings (12,000 segments)
- [x] Cortex Search setup

### 🚧 In Progress (Week 4-6)
- [ ] Multi-agent system (6 agents)
- [ ] Streamlit UI
- [ ] MCP integration

### 📅 Upcoming (Week 7-8)
- [ ] Testing and optimization
- [ ] Final demo preparation
- [ ] Documentation and presentation

### 🔮 Future Enhancements
- Speaker diarization (distinguish host vs guest)
- Multi-language support (Spanish, French)
- Audio clip generation
- Chrome extension
- Real-time episode monitoring

---

## 📈 Performance Metrics

| Metric | Target | Current Status |
|--------|--------|----------------|
| Episodes Indexed | 100+ | ✅ In Progress |
| Searchable Segments | 6,000+ | ✅ In Progress |
| Search Latency (p95) | <5 seconds | ⏳ TBD |
| Embedding Coverage | 100% | ⏳ TBD |
| Snowflake Credits Used | <150 | ⏳ Monitoring |

---

## 🧪 Testing

```bash
# Run DBT tests
cd dbt_podcastiq
dbt test

# Test Cortex Search
# (Run in Snowflake UI)
SELECT * FROM TABLE(
    CORTEX_SEARCH('podcast_search', 'machine learning', {'limit': 5})
);

# Test LangGraph agents
python langgraph_agents/graph.py
```

---

## 🤝 Contributing

This is an academic project for a Gen AI Data Engineering course. Contributions are welcome post-course completion!

### Development Guidelines
- Follow coding standards in `claude.md`
- Update `tasks.md` immediately after completing tasks
- Run DBT tests before committing: `dbt test`
- Use type hints and docstrings in Python code

---

## 📚 Documentation

- **[PRD.md](PRD.md)** - Product Requirements Document
- **[planning.md](planning.md)** - Detailed technical implementation plan
- **[tasks.md](tasks.md)** - Weekly task breakdown and progress tracking
- **[claude.md](claude.md)** - Claude Code session instructions

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Course:** Gen AI Data Engineering with LLM
- **University:** [Your University Name]
- **Professor/TA:** [TA Name]
- **Technologies:**
  - Snowflake Cortex AI for managed LLM and embeddings
  - LangGraph for multi-agent orchestration
  - DBT for data transformation
  - Apache Airflow for workflow orchestration
  - Streamlit for rapid UI development

---

## 📧 Contact

**Developer:** [Your Name]
**Email:** [your.email@university.edu]
**LinkedIn:** [Your LinkedIn]
**GitHub:** [Your GitHub]

---

## 📊 Project Status

**Current Week:** Week 0 (Project Setup)
**Status:** 🟢 On Track
**Next Milestone:** Week 1 - Environment Setup & Proof of Concept

---

**Built with ❤️ using Claude Code**
