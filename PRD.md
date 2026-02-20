# PodcastIQ - Product Requirements Document (PRD)

**Version:** 1.0
**Date:** February 12, 2026
**Project Type:** Gen AI Data Engineering Course Project
**Timeline:** 8 weeks
**Team:** Solo Developer

---

## 1. Project Overview

### 1.1 Executive Summary
PodcastIQ is an AI-powered podcast discovery and analysis platform that makes audio content searchable using semantic search, multi-agent orchestration, and RAG (Retrieval-Augmented Generation) architecture. The platform addresses the fundamental problem that podcast content, despite containing valuable information, is inherently unsearchable in its native audio format.

### 1.2 Problem Statement
- **Scale:** Over 5 million podcasts exist with thousands of hours of valuable content
- **Discovery Challenge:** Users cannot search within episodes for specific topics or moments
- **Time Waste:** Finding relevant discussions requires listening to entire 1-3 hour episodes
- **Lost Value:** Valuable insights remain buried and inaccessible in audio format
- **No Cross-Reference:** Cannot compare how different experts discuss the same subject

### 1.3 Solution
An intelligent search platform that:
- Makes podcast transcripts semantically searchable (search by concept, not just keywords)
- Provides timestamp-precise deep links directly to YouTube moments
- Uses multi-agent AI system to summarize, analyze, and recommend content
- Enables cross-podcast comparisons and topic analysis
- Delivers results in <5 seconds with high relevance accuracy

### 1.4 Project Objectives
**Academic Requirements:**
1. ✅ Demonstrate ETL/ELT data engineering with Airflow, DBT, and Snowflake
2. ✅ Implement production-grade RAG system with vector embeddings
3. ✅ Build agentic AI architecture using LangGraph (6 specialized agents)
4. ✅ Integrate Model Context Protocol (MCP) for enhanced agent capabilities
5. ✅ Showcase Snowflake Cortex AI features (embeddings, LLMs, Cortex Search)

**Technical Learning Goals:**
- Master Snowflake data warehousing and Cortex AI
- Understand multi-agent system design and orchestration
- Gain hands-on experience with modern data engineering tools
- Build production-quality code suitable for portfolio

**Business Value:**
- Create genuinely useful tool (not just academic exercise)
- Solve real user pain point in podcast discovery
- Build foundation for potential startup/SaaS product

---

## 2. Target Users & Use Cases

### 2.1 Primary Users
1. **Software Engineers** - Finding technical discussions on specific frameworks, tools, or concepts
2. **Researchers** - Locating expert opinions and data points across multiple sources
3. **Students** - Building learning paths from podcast content (beginner → advanced)
4. **Content Creators** - Researching how topics have been covered previously

### 2.2 User Stories

**As a software engineer, I want to:**
- Find all discussions about "Rust ownership model" across tech podcasts
- Compare how different experts explain database optimization
- Jump directly to the timestamp where a specific topic is discussed
- Get a summary of key points without watching full episodes

**As a researcher, I want to:**
- Search for expert opinions on "AI safety" across 100 episodes
- Identify common themes and divergent perspectives
- Track how discussions on a topic have evolved over time
- Fact-check claims with real-time web search

**As a student, I want to:**
- Find podcast segments that explain concepts I'm learning
- Get recommendations for episodes that progress from basics to advanced
- Bookmark and organize useful segments for later reference

---

## 3. Functional Requirements

### 3.1 Data Ingestion & Processing

**FR-1: YouTube Transcript Extraction**
- Extract transcripts from 300 YouTube-based podcast episodes
- Target 10-15 channels (~20-30 episodes per channel)
- Support auto-generated and manual captions
- Filter for English-language content only
- Validate minimum transcript length (>100 words)

**FR-2: ETL Pipeline**
- Automated daily extraction via Apache Airflow
- Incremental loading (avoid duplicate transcripts)
- Error handling and retry logic (3 attempts with exponential backoff)
- Failed extraction logging for manual review
- Trigger DBT transformations post-ingestion

**FR-3: Data Transformation (DBT)**
- Clean and normalize raw transcripts
- Chunk episodes into 60-second segments with 15-second overlap
- Generate YouTube deep links with timestamps
- Extract entities and topics using Snowflake Cortex LLMs
- Create multi-level summaries (1-sentence, paragraph, detailed)

**FR-4: Vector Embeddings**
- Generate 768-dimensional embeddings for all segments
- Use Snowflake Cortex `snowflake-arctic-embed-m` model
- Incremental embedding generation (only new segments)
- Store in Snowflake VECTOR column type

### 3.2 Search Functionality

**FR-5: Semantic Search**
- Hybrid search combining vector similarity + keyword matching
- Support natural language queries ("How do neural networks work?")
- Return top 10 results ranked by relevance score
- Include metadata: channel, episode title, timestamp, text snippet
- Search latency <5 seconds (preferably <2 seconds)

**FR-6: Filtering & Refinement**
- Filter by channel (e.g., show only Lex Fridman results)
- Filter by topic/entity (e.g., show only "AI" discussions)
- Filter by date range (e.g., episodes from 2025-2026)
- Sort by relevance, date, or channel

**FR-7: Context Retrieval**
- For each search result, retrieve adjacent segments (before/after)
- Provide richer context to LLM for better summarization
- Link segments using `previous_segment_id` and `next_segment_id`

### 3.3 Multi-Agent System

**FR-8: Router Agent (MVP)**
- Analyze user query intent
- Route to appropriate specialist agent (Search, Summarize, Compare, etc.)
- Handle conversational context and state management
- Conditionally route to MCP tools for debugging or web search

**FR-9: Search Agent (MVP)**
- Execute Snowflake Cortex Search queries
- Retrieve top-K relevant segments
- Return results with relevance scores and metadata
- Handle empty results gracefully

**FR-10: Summarization Agent (MVP)**
- Generate concise 2-3 sentence summaries from search results
- Extract key insights and best quotes
- Append YouTube timestamp links
- Use Snowflake Cortex `llama3.1-405b` LLM

**FR-11: Topic Extraction Agent (Stretch)**
- Identify named entities (people, organizations, technologies)
- Extract key topics and themes from segments
- Perform sentiment analysis per topic
- Store in `semantic.topics_entities` table

**FR-12: Comparison Agent (Stretch)**
- Compare how different podcasters discuss the same topic
- Identify common themes, unique perspectives, contradictions
- Generate side-by-side comparison view
- Highlight agreement/divergence points

**FR-13: Recommendation Agent (Stretch)**
- Content-based filtering using topic embeddings
- Suggest "Related Episodes" based on current search
- Personalize recommendations based on search history
- Generate learning paths (beginner → advanced)

### 3.4 MCP Integration

**FR-14: Filesystem MCP Server**
- Read Airflow logs for debugging DAG failures
- Access raw transcript files for inspection
- Enable "Why did the DAG fail?" queries from users
- Integrate as LangChain tool in Router Agent

**FR-15: Web Search MCP Server**
- Real-time web search for fact-checking podcast claims
- Query format: "Is [claim from episode X] still accurate?"
- Use Brave Search API or alternative (free tier)
- Return top 3 relevant web results

**FR-16: MCP Tool Routing**
- Router Agent decides when to use MCP tools vs podcast search
- Keywords: "debug", "current", "latest", "recent" trigger MCP
- MCP tool calls complete in <3 seconds
- Graceful fallback if MCP unavailable

### 3.5 User Interface

**FR-17: Search Interface (Streamlit)**
- Clean search bar with placeholder "Search 300+ podcast episodes..."
- Auto-suggest topics as user types (optional stretch)
- Support multi-line queries (advanced use cases)
- "Search" button and Enter key submit

**FR-18: Results Display**
- Card-based layout for each search result
- Display: Episode title, channel name, segment text preview (150 chars), timestamp, relevance score
- Clickable YouTube deep link (opens at exact timestamp)
- Topic tags (color-coded badges)
- "Show more context" expands to adjacent segments

**FR-19: Filters & Sidebar**
- Channel filter (checkboxes for each of 10 channels)
- Topic filter (extracted from `topics_entities`)
- Date range slider
- "Clear all filters" button

**FR-20: Episode Summaries**
- Dedicated page for full episode view
- Multi-level summaries (TLDR, executive summary, detailed)
- Key moments timeline
- Best quotes section
- "Related Episodes" recommendations

**FR-21: Comparison View**
- Side-by-side comparison of 2+ podcasters on same topic
- Venn diagram or table format showing common themes/differences
- Links to specific segments supporting each point
- Export comparison as PDF or shareable link (stretch)

---

## 4. Non-Functional Requirements

### 4.1 Performance

**NFR-1: Search Latency**
- 95th percentile query response time <5 seconds
- Target: <2 seconds for most queries
- Caching for repeated queries (Snowflake 24-hour cache)

**NFR-2: Data Processing**
- Initial 100-episode ingestion complete in <2 weeks
- Daily incremental updates process in <30 minutes
- DBT transformations complete in <1 hour

**NFR-3: UI Responsiveness**
- Streamlit page load <2 seconds
- Search result rendering <1 second after receiving data
- Smooth scrolling and filtering (no lag)

### 4.2 Scalability

**NFR-4: Data Volume**
- Support 100-200 episodes without performance degradation
- Storage: <150MB total (well within Snowflake free tier)
- Handle 10,000-20,000 searchable segments

**NFR-5: Concurrent Users**
- Streamlit supports 1-5 concurrent users (sufficient for demo)
- Snowflake auto-scales warehouses as needed
- Future: migrate to production-grade deployment

### 4.3 Reliability

**NFR-6: Data Quality**
- 80%+ successful transcript extraction rate
- DBT tests ensure data integrity (no null values, valid timestamps)
- Automated data quality monitoring

**NFR-7: Error Handling**
- Graceful degradation if LLM unavailable
- Clear error messages to users
- Airflow retry logic prevents data loss

**NFR-8: Monitoring**
- Weekly Snowflake credit usage reports
- Airflow DAG success/failure alerts
- Track search query performance metrics

### 4.4 Cost

**NFR-9: Budget Constraints**
- Total Snowflake credits: <150 (out of 200 free credits)
- Target cost: $250-$300 (well within $400 budget)
- Zero external API costs (use Cortex LLMs only)
- Free YouTube transcript extraction

**NFR-10: Cost Optimization**
- Aggressive warehouse auto-suspend (60-300 seconds)
- Use X-SMALL warehouses for most operations
- Incremental DBT models (reduce redundant processing)
- Streamlit caching to minimize Snowflake queries

### 4.5 Security & Privacy

**NFR-11: Data Privacy**
- Only public YouTube podcasts (no private content)
- No user authentication required (demo app)
- No PII collection or storage
- Search history stored anonymously (session IDs only)

**NFR-12: Credentials Management**
- Store Snowflake credentials in `.env` file (not committed to git)
- Use Airflow Connections UI for secure credential storage
- Rotate credentials periodically (monthly)

### 4.6 Maintainability

**NFR-13: Code Quality**
- Modular architecture (separate Airflow, DBT, LangGraph, Streamlit)
- Type hints in Python code
- Docstrings for all functions
- README with setup instructions

**NFR-14: Version Control**
- Git repository with clear commit messages
- `.gitignore` excludes sensitive files (.env, credentials)
- Branching strategy: `main` (stable), `dev` (active development)

**NFR-15: Documentation**
- Architecture diagram in README
- Weekly progress updates for professor
- Inline code comments for complex logic
- `tasks.md` tracks implementation progress

---

## 5. Success Criteria & KPIs

### 5.1 Technical Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Episodes Indexed | 300+ | `SELECT COUNT(*) FROM curated.curated_episodes` |
| Searchable Segments | 18,000+ | `SELECT COUNT(*) FROM curated.curated_segments` |
| Embedding Coverage | 100% | All segments have embeddings in `semantic.embeddings` |
| Search Latency (p95) | <5 seconds | Monitor Streamlit query times |
| Search Relevance | >80% top-3 accuracy | Manual evaluation on 20 test queries |
| Snowflake Credits Used | <150 credits | `WAREHOUSE_METERING_HISTORY` query |
| Agent Response Quality | >4/5 rating | Professor/user feedback on demo |

### 5.2 Academic Success Criteria

✅ **Data Engineering:** Fully automated ETL pipeline with Airflow + DBT
✅ **RAG Implementation:** Semantic search with vector embeddings + context retrieval
✅ **Agentic AI:** 6 functional agents orchestrated via LangGraph
✅ **MCP Integration:** Filesystem + Web Search MCP tools operational
✅ **Snowflake Cortex:** Uses embeddings, LLMs, and Cortex Search

### 5.3 Demo Readiness

**Week 8 Deliverables:**
- ✅ Live Streamlit app demonstrates all features
- ✅ 10-minute presentation with slides
- ✅ 5 example queries showcasing different agents
- ✅ GitHub repository with clean, documented code
- ✅ Final report (5-10 pages) with architecture + learnings
- ✅ Backup demo video (in case live demo fails)

---

## 6. Technical Constraints

### 6.1 Technology Stack (Fixed)

| Component | Technology | Constraint |
|-----------|-----------|------------|
| Data Warehouse | Snowflake | University-provided access |
| LLM/AI | Snowflake Cortex | llama3.1-405b, Arctic embeddings |
| Orchestration | Apache Airflow | Local via Astro CLI |
| Transformation | DBT | dbt-snowflake adapter |
| Agent Framework | LangGraph | Python-based |
| Frontend | Streamlit | Python-based |
| Data Source | YouTube Transcript API | Free, no API key |
| MCP | @modelcontextprotocol/sdk | Node.js + Python |

### 6.2 Time Constraints
- **Timeline:** 8 weeks (February - April 2026)
- **Solo developer:** No team delegation
- **Weekly check-ins:** Professor expects progress updates
- **Learning curve:** 4+ new technologies to master simultaneously

### 6.3 Data Constraints
- **100 episodes total:** ~10 per channel across 10 channels
- **English only:** Auto-captions must be English
- **Public content only:** YouTube videos with transcripts enabled
- **Transcript quality:** Accept ~90% accuracy from auto-captions

### 6.4 Infrastructure Constraints
- **Local development:** No cloud deployment budget
- **Snowflake free tier:** $400 credit limit (200 credits × $2)
- **Airflow local:** Runs on developer machine, not production cluster
- **Streamlit local:** Localhost deployment (optional: streamlit.io free tier)

---

## 7. Out of Scope (Future Enhancements)

The following features are **not required** for the 8-week project but could be added post-course:

1. **Speaker Diarization** - Distinguish between host and guest speakers
2. **Multi-Language Support** - Spanish, French, Hindi podcasts
3. **Audio Clip Generation** - Auto-generate shareable audio/video clips
4. **Chrome Extension** - Search podcasts while browsing YouTube
5. **Collaborative Filtering** - User-based recommendations (requires user accounts)
6. **Creator Analytics Dashboard** - Insights for podcast creators
7. **Custom MCP Server** - Expose PodcastIQ search as tool for other LLM apps
8. **Real-Time Monitoring** - Auto-ingest new episodes daily
9. **Whisper Re-Transcription** - Improve transcript quality using OpenAI Whisper

---

## 8. Dependencies & Assumptions

### 8.1 External Dependencies
- **Snowflake Access:** University provides free account (assumed available)
- **YouTube Transcripts:** Podcasts have auto-generated captions (70-80% success rate expected)
- **Python 3.9+:** Local development environment
- **Node.js 16+:** Required for MCP servers
- **Git:** Version control

### 8.2 Assumptions
- Snowflake free tier credits are sufficient ($400 budget)
- Auto-generated YouTube captions are acceptable quality (~90% accuracy)
- 100 episodes from 10 channels is feasible in 2 weeks
- Local Airflow can handle 100-episode processing without issues
- Streamlit localhost deployment is acceptable for academic demo

### 8.3 Risks & Mitigation
See detailed risk matrix in planning.md (Risk Mitigation section)

---

## 9. Stakeholders

| Role | Name | Responsibility |
|------|------|----------------|
| Developer | [Your Name] | Full implementation, weekly updates |
| Professor/TA | [TA Name] | Review progress, provide feedback, grade project |
| End Users | Classmates, demo audience | Provide feedback on usability and value |

---

## 10. Timeline Overview

| Week | Milestone | Key Deliverable |
|------|-----------|-----------------|
| 1 | Environment Setup | 5 episodes in Snowflake |
| 2 | Full ETL Pipeline | 100 episodes extracted |
| 3 | Embeddings & Search | Cortex Search operational |
| 4 | MVP Agents | 3 agents working (Router, Search, Summarize) |
| 5 | Streamlit UI | User interface deployed |
| 6 | Full Agent System + MCP | 6 agents + MCP integration |
| 7 | Testing & Optimization | Production-ready code |
| 8 | Demo & Presentation | Final presentation to class |

Detailed week-by-week tasks are tracked in `tasks.md`.

---

## 11. Approval & Sign-Off

**Document Version:** 1.0
**Created:** February 12, 2026
**Status:** ✅ Approved

This PRD aligns with the approved implementation plan in `planning.md`.

**Next Steps:**
1. ✅ Project structure created
2. ⏳ Begin Week 1: Environment setup
3. ⏳ Extract 5-10 episodes for proof of concept

---

**References:**
- `planning.md` - Detailed technical implementation plan
- `tasks.md` - Weekly task breakdown and progress tracking
- `claude.md` - Session instructions for future development
