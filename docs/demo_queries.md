# PodcastIQ — Demo Query Reference

Tested and confirmed working queries for each agent.
Add new working queries here as you test them.

---

## 1. Search Agent
**Trigger:** User wants specific clips, quotes, or moments about a topic.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `What did experts say about AGI?` | Returns source cards with YouTube links |
| ✅ | `Find clips about machine learning` | Cortex Search hybrid retrieval |

---

## 2. Summarization Agent
**Trigger:** User wants to learn about a topic — knowledge/information questions.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `What are the best strategies for building a startup?` | Synthesizes views across episodes |
| ✅ | `What do experts say about longevity?` | Good for showing multi-channel synthesis |

---

## 3. Temporal Analysis Agent
**Trigger:** How claims or opinions have evolved or changed over time.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `How has Marc Andreessen changed his views on innovation?` | 4 same-speaker evolution pairs, clean cards |

---

## 4. Fact-Check Agent
**Trigger:** Verify whether a specific claim is true, false, or outdated.

| # | Query | Result | Brave Used? | Notes |
|---|-------|--------|-------------|-------|
| ✅ | `Fact check: GPT-5 was released in 2024` | ❌ FALSE | No (LLM confident) | LLM-only path |
| ✅ | `Fact check: Sam Altman was fired from OpenAI in November 2023` | ✅ VERIFIED | Yes (5 web sources) | Brave Search path, shows Wikipedia + CNBC + Livemint links |

---

## 5. Comparison Agent
**Trigger:** Compare viewpoints of two specific people or channels on a topic.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `Compare Sam Altman and Lex Fridman on AI` | Both speakers shown, grouped by speaker with claim type badges |
| 🔲 | `Compare a16z and Huberman Lab on health` | Channel comparison alternative |

---

## 6. Recommendation Agent
**Trigger:** User explicitly wants episode/show suggestions to watch or listen to.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `Recommend episodes about longevity and health` | Returns deduplicated episodes across FoundMyFitness, Knowledge Project, Huberman |
| 🔲 | `Show me episodes with Sam Altman` | Guest-based recommendation |

---

## 7. Insight Agent
**Trigger:** Meta-analysis about channels, speakers, or statistics across the corpus.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `Which podcast channel has the most contradicted claims?` | Returns ranked table: Diary of a CEO (52), Huberman (50), All-In (43) — great demo data |
| 🔲 | `What are the most debated topics across all podcasts?` | — |

---

## 8. Knowledge Graph Agent
**Trigger:** Questions about relationships, appearances, networks between people/topics.

| # | Query | Notes |
|---|-------|-------|
| ✅ | `Who has Sam Altman appeared with across podcasts?` | Names co-appearances with counts — Casey Newton & Kevin Roose (3x), Harj Taggar & Garry Tan (2x), a16z joint appearance |

---

## Router Classification Reference

| Query pattern | Classified as |
|---------------|---------------|
| "What are strategies / tips / advice about X?" | SUMMARIZE |
| "Find clips / What did X say about Y?" | SEARCH |
| "Recommend / suggest / show me episodes about X" | RECOMMEND |
| "Compare X vs Y on Z" | COMPARE |
| "How has X changed over time / who changed their mind?" | TEMPORAL |
| "Fact check: …" / "Is it true that…?" | FACTCHECK |
| "Which channel has most X / credibility report" | INSIGHT |
| "Who appeared with X / show X's network" | GRAPH |

---

*Update this file after each test run. Mark ✅ when confirmed working, ❌ if broken (add bug notes).*
