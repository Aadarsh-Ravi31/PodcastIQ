# Claude Code Session Instructions for PodcastIQ

**Last Updated:** February 12, 2026

This file contains instructions for Claude Code to follow when working on the PodcastIQ project across multiple sessions. These guidelines ensure consistency, track progress, and maintain project context.

---

## 🚨 CRITICAL: Session Startup Protocol

**At the START of EVERY conversation, you MUST:**

### 1. Read `planning.md` (Required)
```
Read planning.md to understand the full project architecture, design decisions, and 8-week implementation plan.
```
- **Why:** Provides complete context on project goals, technology stack, and approved architecture
- **Location:** `D:\Projects\PodcastIQ\planning.md`
- **Key Sections to Review:**
  - High-Level Architecture
  - Snowflake Schema Design (4-layer architecture)
  - Multi-Agent Architecture (6 agents)
  - 8-Week Implementation Plan
  - Key Design Decisions

### 2. Check `tasks.md` (Required)
```
Read tasks.md to see current progress, next priorities, and identify the current week.
```
- **Why:** Shows what's completed, what's in progress, and what's next
- **Location:** `D:\Projects\PodcastIQ\tasks.md`
- **What to Look For:**
  - Current week status (e.g., "Week 3: Chunking & Embeddings - In Progress")
  - Incomplete tasks marked with `[ ]`
  - Blockers or questions documented
  - Progress tracking table

### 3. Check `PRD.md` (As Needed)
```
Read PRD.md when you need to understand functional requirements or success criteria.
```
- **Why:** Defines product requirements, user stories, and acceptance criteria
- **Location:** `D:\Projects\PodcastIQ\PRD.md`
- **When to Read:**
  - Starting a new feature
  - Clarifying requirements
  - Writing tests (refer to success criteria)

---

## ✅ Session Working Protocol

### During Every Work Session:

**1. Update `tasks.md` Immediately**
- **Mark tasks as completed:** Change `[ ]` to `[x]` AS SOON AS you finish a task
- **Don't batch updates:** Update after EACH task completion, not at end of session
- **Example:**
  ```markdown
  Before: - [ ] Create embeddings.sql model
  After:  - [x] Create embeddings.sql model
  ```

**2. Document Blockers**
- If you encounter a blocker (missing credentials, unclear requirement, etc.), add to "Notes & Blockers" section in `tasks.md`
- Example:
  ```markdown
  **Blockers:**
  - Snowflake credentials not found in .env file (waiting for user to provide)
  ```

**3. Track Progress**
- Update "Progress Tracking" table in `tasks.md` when a week is completed
- Example:
  ```markdown
  | Week | Status | Start Date | End Date | Notes |
  | 1 | Completed | Feb 15 | Feb 21 | All 5 POC episodes loaded successfully |
  ```

---

## 📁 Project Structure

```
D:\Projects\PodcastIQ/
├── PRD.md                          # Product Requirements Document
├── planning.md                     # Technical implementation plan (approved)
├── tasks.md                        # Weekly task breakdown (update this!)
├── claude.md                       # This file - session instructions
├── README.md                       # Public-facing project overview
├── .env                            # Environment variables (NEVER commit)
├── .gitignore                      # Git ignore patterns
├── requirements.txt                # Python dependencies
├── airflow/                        # Apache Airflow DAGs
│   └── dags/
│       ├── youtube_extract_dag.py
│       ├── dbt_transform_dag.py
│       └── embedding_generation_dag.py
├── dbt_podcastiq/                  # DBT project
│   ├── models/
│   │   ├── curated/
│   │   │   ├── curated_episodes.sql
│   │   │   └── curated_segments.sql
│   │   ├── semantic/
│   │   │   ├── embeddings.sql
│   │   │   └── topics_entities.sql
│   │   └── app/
│   ├── tests/
│   └── dbt_project.yml
├── langgraph_agents/               # LangGraph multi-agent system
│   ├── agents/
│   │   ├── router.py
│   │   ├── search.py
│   │   ├── summarization.py
│   │   ├── topic_extraction.py
│   │   ├── comparison.py
│   │   └── recommendation.py
│   ├── state.py                    # PodcastIQState definition
│   └── graph.py                    # Workflow orchestration
├── streamlit_app/                  # Streamlit frontend
│   ├── app.py                      # Main entry point
│   └── components/
│       ├── search_bar.py
│       ├── results_display.py
│       └── filters.py
└── sql/                            # SQL scripts for Snowflake
    ├── schema_setup.sql
    └── cortex_search_setup.sql
```

---

## 🛠️ Technology Stack Reference

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| Data Warehouse | Snowflake | Latest | Storage, compute, vector search |
| LLM/AI | Snowflake Cortex | llama3.1-405b, Arctic Embed | Embeddings, summarization, entity extraction |
| Orchestration | Apache Airflow | 2.10.0 | ETL automation |
| Transformation | DBT | 1.8.0 | SQL-based data modeling |
| Agent Framework | LangGraph | 0.2.28 | Multi-agent orchestration |
| Frontend | Streamlit | 1.38.0 | Web UI |
| Data Source | YouTube Transcript API | 0.6.2 | Free podcast transcripts |
| MCP | @modelcontextprotocol/sdk | 0.9.0 | Filesystem + Web Search tools |

---

## 🎯 Coding Standards & Conventions

### Python Code Style

**1. Type Hints (Required)**
```python
# Good
def search_podcasts(query: str, limit: int = 10) -> List[dict]:
    pass

# Bad
def search_podcasts(query, limit=10):
    pass
```

**2. Docstrings (Google Style)**
```python
def chunk_transcript(text: str, window_seconds: int = 60, overlap_seconds: int = 15) -> List[dict]:
    """
    Chunk podcast transcript into time-based windows with overlap.

    Args:
        text: Full episode transcript
        window_seconds: Size of each chunk in seconds (default: 60)
        overlap_seconds: Overlap between chunks in seconds (default: 15)

    Returns:
        List of dictionaries containing chunk text, start_time, end_time

    Raises:
        ValueError: If window_seconds < overlap_seconds
    """
    pass
```

**3. Error Handling**
```python
# Always handle exceptions gracefully
try:
    transcript = fetch_youtube_transcript(video_id)
except TranscriptNotAvailableError:
    logger.error(f"Transcript not available for video {video_id}")
    return None
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise
```

**4. Logging (Use Python logging module)**
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Starting transcript extraction")   # Detailed debugging
logger.info("Extracted 50 episodes")            # General info
logger.warning("Transcript quality low")        # Warnings
logger.error("Failed to connect to Snowflake")  # Errors
```

### SQL Style (DBT Models)

**1. Model Naming:**
- Curated layer: `curated_<entity>.sql` (e.g., `curated_episodes.sql`)
- Semantic layer: Descriptive names (e.g., `embeddings.sql`, `topics_entities.sql`)
- Lowercase with underscores

**2. SQL Formatting:**
```sql
-- Good: Readable, formatted
SELECT
    episode_id,
    episode_title,
    COUNT(*) AS segment_count,
    AVG(word_count) AS avg_words_per_segment
FROM {{ ref('curated_segments') }}
GROUP BY episode_id, episode_title
ORDER BY segment_count DESC;

-- Bad: Single line, hard to read
SELECT episode_id,episode_title,COUNT(*) AS segment_count,AVG(word_count) AS avg_words_per_segment FROM curated_segments GROUP BY episode_id,episode_title ORDER BY segment_count DESC;
```

**3. Use DBT Refs (Not Hardcoded Tables):**
```sql
-- Good
FROM {{ ref('curated_episodes') }}

-- Bad
FROM curated.curated_episodes
```

### LangGraph Conventions

**1. State Schema:**
```python
from typing import TypedDict, List, Annotated
import operator

class PodcastIQState(TypedDict):
    user_query: str
    query_type: str  # 'search', 'summarize', 'compare'
    search_results: List[dict]
    summary: str
    messages: Annotated[List[str], operator.add]  # Conversation history
```

**2. Agent Function Signature:**
```python
def search_agent(state: PodcastIQState) -> dict:
    """
    Search agent executes Cortex Search queries.

    Args:
        state: Current graph state

    Returns:
        Dictionary with updated state keys (search_results, messages)
    """
    # Implementation
    return {
        "search_results": results,
        "messages": ["Search: Found 5 relevant segments"]
    }
```

---

## 🔧 Common Commands & Workflows

### Environment Setup

```bash
# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install MCP servers (Node.js)
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-brave-search
```

### Airflow

```bash
# Start Airflow (Astro CLI)
astro dev start

# Stop Airflow
astro dev stop

# View Airflow logs
astro dev logs

# Trigger DAG manually
# (Use Airflow UI: localhost:8080)
```

### DBT

```bash
# Navigate to DBT project
cd dbt_podcastiq

# Run all models
dbt run

# Run specific model
dbt run --models curated_segments

# Run tests
dbt test

# Run specific test
dbt test --models curated_segments

# Generate documentation
dbt docs generate
dbt docs serve
```

### Snowflake

```bash
# Connect via snowsql (CLI)
snowsql -a <account> -u <user>

# Or use Snowflake Web UI
# https://<account>.snowflakecomputing.com
```

**Useful Queries:**

```sql
-- Check credit usage (weekly)
SELECT
    WAREHOUSE_NAME,
    SUM(CREDITS_USED) AS total_credits,
    SUM(CREDITS_USED) * 2 AS cost_usd
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE START_TIME >= DATEADD(day, -7, CURRENT_TIMESTAMP())
GROUP BY WAREHOUSE_NAME;

-- Check data pipeline progress
SELECT
    (SELECT COUNT(*) FROM raw.raw_transcripts) AS raw_transcript_count,
    (SELECT COUNT(*) FROM curated.curated_episodes) AS curated_episodes_count,
    (SELECT COUNT(*) FROM curated.curated_segments) AS curated_segments_count,
    (SELECT COUNT(*) FROM semantic.embeddings) AS embeddings_count;

-- Test Cortex Search
SELECT * FROM TABLE(
    CORTEX_SEARCH('podcast_search', 'machine learning', {'limit': 5})
);
```

### Streamlit

```bash
# Run Streamlit app
cd streamlit_app
streamlit run app.py

# App opens at: http://localhost:8501

# Clear cache (if needed)
streamlit cache clear
```

### Git

```bash
# Check status
git status

# Add files
git add .

# Commit
git commit -m "Implement curated_segments chunking logic"

# Push
git push origin main

# Create new branch for feature
git checkout -b feature/topic-extraction-agent
```

---

## 📚 Key Documentation Links

### Snowflake
- [Snowflake Documentation](https://docs.snowflake.com/en/index)
- [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions)
- [Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Vector Embeddings](https://docs.snowflake.com/en/user-guide/snowflake-cortex/vector-embeddings)

### DBT
- [DBT Documentation](https://docs.getdbt.com/)
- [DBT Best Practices](https://docs.getdbt.com/docs/best-practices)
- [DBT Snowflake Adapter](https://docs.getdbt.com/reference/warehouse-setups/snowflake-setup)

### LangGraph
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Multi-Agent Workflows](https://blog.langchain.com/langgraph-multi-agent-workflows/)

### YouTube Transcript API
- [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api)

### Airflow
- [Apache Airflow Documentation](https://airflow.apache.org/docs/)
- [Astronomer (Astro CLI)](https://docs.astronomer.io/astro/cli/overview)

### Streamlit
- [Streamlit Documentation](https://docs.streamlit.io/)
- [Streamlit Caching](https://docs.streamlit.io/library/advanced-features/caching)

---

## ⚠️ Important Reminders

### Cost Management
- **Monitor Snowflake credits weekly** (target: <150 credits total)
- **Use X-SMALL warehouses** for most operations
- **Auto-suspend is critical:** All warehouses set to 60-300 second idle timeout
- **Incremental DBT models:** Only process new data (reduces Cortex API costs)

### Data Quality
- **Run DBT tests regularly:** `dbt test` after every model change
- **Validate transcript quality:** Accept ~90% accuracy from auto-captions
- **Check embedding coverage:** All segments must have embeddings before Cortex Search setup

### Security
- **NEVER commit `.env` file** to Git (contains Snowflake credentials)
- **Use Airflow Connections UI** for storing credentials, not hardcoded in DAGs
- **Snowflake credentials in `~/.dbt/profiles.yml`** for DBT (not in code)

### Weekly Professor Updates
- **Send update every Friday** (or as required by course)
- **Include:**
  - What was completed this week (check tasks.md)
  - Demo/screenshot of working feature
  - Any blockers or questions
  - Next week's plan

---

## 🐛 Troubleshooting Guide

### Common Issues

**Issue: Snowflake connection fails from DBT**
```bash
# Check profiles.yml configuration
cat ~/.dbt/profiles.yml

# Test connection
dbt debug

# Verify credentials in .env
cat .env
```

**Issue: Airflow DAG not appearing in UI**
```bash
# Check DAG file for syntax errors
python airflow/dags/youtube_extract_dag.py

# Restart Airflow
astro dev restart
```

**Issue: YouTube transcript extraction fails**
```python
# Check if video has transcripts enabled
from youtube_transcript_api import YouTubeTranscriptApi

try:
    transcript = YouTubeTranscriptApi.get_transcript("video_id", languages=['en'])
    print("Transcript available")
except:
    print("No transcript available")
```

**Issue: Cortex Search returns no results**
```sql
-- Check if search service exists
SHOW CORTEX SEARCH SERVICES;

-- Verify embeddings exist
SELECT COUNT(*) FROM semantic.embeddings;

-- Check service status
DESCRIBE CORTEX SEARCH SERVICE podcast_search;
```

**Issue: Streamlit app won't start**
```bash
# Check for port conflicts
lsof -i :8501  # Mac/Linux
netstat -ano | findstr :8501  # Windows

# Clear Streamlit cache
streamlit cache clear

# Reinstall Streamlit
pip uninstall streamlit
pip install streamlit==1.38.0
```

---

## 📝 Session Checklist Template

Use this checklist at the start of each coding session:

```markdown
## Session: [Date] - [Brief Description]

### Pre-Work
- [ ] Read planning.md (if first session or after break)
- [ ] Read tasks.md to identify current week and next task
- [ ] Check for blockers in tasks.md
- [ ] Activate virtual environment: `venv\Scripts\activate`

### During Work
- [ ] Mark tasks as completed in tasks.md immediately (don't batch)
- [ ] Document any blockers or questions in tasks.md
- [ ] Follow coding standards (type hints, docstrings, logging)
- [ ] Run tests after making changes (DBT tests, unit tests)

### Post-Work
- [ ] Update Progress Tracking table in tasks.md if week completed
- [ ] Commit and push code to Git
- [ ] Document lessons learned (if any) in tasks.md "Notes & Blockers"
- [ ] Plan next session's focus
```

---

## 🎯 Success Criteria Quick Reference

Refer to `PRD.md` Section 5 for full details. Key metrics:

| Metric | Target |
|--------|--------|
| Episodes Indexed | 100+ |
| Searchable Segments | 6,000+ |
| Embedding Coverage | 100% |
| Search Latency (p95) | <5 seconds |
| Snowflake Credits Used | <150 |
| All Agents Functional | 6/6 |

---

**Remember:** This file is your guide. Read `planning.md` and `tasks.md` first, then code. Update `tasks.md` immediately. Ask questions if requirements are unclear. Document learnings for future you.

Happy coding! 🚀
