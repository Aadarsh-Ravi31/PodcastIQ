# PodcastIQ — Data Flow Diagrams

> Comprehensive diagrams covering every stage of the PodcastIQ pipeline:
> Extraction → Transformation → Embedding → Retrieval → Generation → Output

---

## Diagram 1 — End-to-End System Overview

```mermaid
flowchart TD
    subgraph SOURCES["🌐 DATA SOURCES  (25 Channels · 6 Genres · 286 Episodes)"]
        direction LR
        YT["YouTube\n(25 Channels)"]
        GEN1["Tech / AI\n(Lex Fridman, All-In, a16z)"]
        GEN2["Health / Science\n(Huberman, FoundMyFitness)"]
        GEN3["Business / VC\n(Acquired, Diary of a CEO)"]
        YT --> GEN1 & GEN2 & GEN3
    end

    subgraph EXTRACT["⬇ STAGE 1 — EXTRACTION"]
        EXT["channel_extraction.py\n(yt-dlp + YouTube Data API v3)"]
        META["metadata.json\nTitle, date, guests, duration"]
        TRANS["transcript.json\nWebVTT auto-captions\n~90% accuracy"]
        EXT --> META & TRANS
    end

    subgraph LOAD["📦 STAGE 2 — LOAD  (Snowflake RAW)"]
        LOADER["snowflake_loader.py\nPUT → COPY INTO\nKey-pair auth"]
        RAW_EP["RAW.EPISODES\nVARIANT column\n1 row per video"]
        RAW_CH["RAW.CHANNELS\n25 channel records"]
        LOADER --> RAW_EP & RAW_CH
    end

    subgraph TRANSFORM["🔧 STAGE 3 — TRANSFORM  (Snowflake STAGING + CURATED)"]
        STG_EP["STG_EPISODES view\n22 flat typed columns\nfrom VARIANT"]
        STG_SEG["STG_SEGMENTS view\nLATERAL FLATTEN\n1 row per transcript line"]
        INT_EP["INT_EPISODES view\n+ TRANSCRIPT_QUALITY\n+ ENGAGEMENT_RATE"]
        INT_SEG["INT_SEGMENTS view\n+ YOUTUBE_TIMESTAMP_URL\n+ WORD_COUNT"]
        CUR["CUR_CHUNKS table\n120s sliding windows\n15s overlap\n13,807 chunks"]
        STG_EP --> INT_EP
        STG_SEG --> INT_SEG
        INT_EP & INT_SEG --> CUR
    end

    subgraph ENRICH["🧠 STAGE 4 — ENRICH  (Snowflake SEMANTIC)"]
        direction TB
        EMBED["SEM_CHUNK_EMBEDDINGS\nArctic-embed-m\n768-dim VECTOR\n13,807 vectors"]
        TOPICS["SEM_CHUNK_TOPICS\nCortex LLM\nllama3.1-70b\n2-5 topics/chunk"]
        ENTITIES["SEM_CHUNK_ENTITIES\nNamed Entity Recognition\nPeople · Orgs · Tech"]
        SUMMARIES["SEM_EPISODE_SUMMARIES\nEpisode-level summaries\n286 summaries"]
        CLAIMS["SEM_CLAIMS\nStructured claim extraction\n84,260 claims\nSpeaker attribution"]
        PARTICIPANTS["SEM_EPISODE_PARTICIPANTS\n683 host/guest records\nTitle-parse + LLM inference"]
        EVOLUTION["SEM_CLAIM_EVOLUTION\n823 evolution pairs\nCONTRADICTED · ESCALATED\nCONFIRMED · SOFTENED · REVISED"]
    end

    subgraph INDEX["🔍 STAGE 5 — INDEX"]
        CORTEX_SEARCH["Cortex Search Service\nPODCASTIQ_SEARCH\nHybrid vector + BM25\nAuto re-ranking"]
        NEO4J["Neo4j Knowledge Graph\n88,823 nodes\n253,740 relationships\nPerson · Episode · Topic · Claim"]
    end

    subgraph AGENTS["🤖 STAGE 6 — MULTI-AGENT REASONING  (LangGraph)"]
        ROUTER["Router Agent\nllama3.1-8b\n87.5% accuracy\n8 query types"]
        SEARCH_A["Search Agent"]
        SUMM_A["Summarization Agent"]
        KG_A["Knowledge Graph Agent"]
        TEMP_A["Temporal Agent"]
        FACT_A["Fact-Check Agent"]
        COMP_A["Comparison Agent"]
        REC_A["Recommendation Agent"]
        INS_A["Insight Agent"]
        ROUTER --> SEARCH_A & SUMM_A & KG_A & TEMP_A & FACT_A & COMP_A & REC_A & INS_A
    end

    subgraph OUTPUT["🖥 STAGE 7 — OUTPUT  (Streamlit UI)"]
        CHAT["Chat Interface\nSource cards · YouTube links"]
        GRAPH_UI["Graph Explorer\npyvis force-directed\nreal-time query"]
        DASH["Channel Dashboard\nTopic charts · Guest grids"]
    end

    SOURCES --> EXTRACT
    EXTRACT --> LOAD
    LOAD --> TRANSFORM
    TRANSFORM --> ENRICH
    ENRICH --> INDEX
    INDEX --> AGENTS
    AGENTS --> OUTPUT

    style SOURCES fill:#1e1e2e,color:#cdd6f4,stroke:#585b70
    style EXTRACT fill:#1e293b,color:#e2e8f0,stroke:#334155
    style LOAD fill:#1a1a2e,color:#e2e8f0,stroke:#334155
    style TRANSFORM fill:#0f2027,color:#e2e8f0,stroke:#334155
    style ENRICH fill:#0d1117,color:#e2e8f0,stroke:#30363d
    style INDEX fill:#161b22,color:#e2e8f0,stroke:#30363d
    style AGENTS fill:#12141a,color:#e2e8f0,stroke:#30363d
    style OUTPUT fill:#1a1625,color:#e2e8f0,stroke:#30363d
```

---

## Diagram 2 — Detailed Extraction & Ingestion Pipeline

```mermaid
flowchart LR
    subgraph SRC["YouTube Source"]
        VID["Video ID\ne.g. dQw4w9WgXcQ"]
        YTDLP["yt-dlp\nDownload WebVTT\nauto-captions"]
        YTAPI["YouTube Data API v3\nFetch metadata\nTitle · Date · Description"]
        VID --> YTDLP & YTAPI
    end

    subgraph LOCAL["Local Processing"]
        VTT["WebVTT file\nTimestamped transcript\n[00:00:15.000] Hello..."]
        PARSE["vtt_parser.py\nMerge cue lines\nClean artifacts [Music][Applause]"]
        META_JSON["metadata.json\n{title, channel, publish_date,\nduration, description, tags}"]
        TRANS_JSON["transcript.json\n{video_id, segments: [\n  {text, start, duration}\n]}"]
        YTDLP --> VTT
        VTT --> PARSE
        YTAPI --> META_JSON
        PARSE --> TRANS_JSON
    end

    subgraph MERGE["Merge & Stage"]
        MERGED["Merged payload\n{metadata + transcript\nin single VARIANT}"]
        PUT["PUT command\nUpload to Snowflake stage\n@PODCASTIQ_STAGE"]
        COPY["COPY INTO RAW.EPISODES\nParse JSON → VARIANT\n~50ms per episode"]
        META_JSON & TRANS_JSON --> MERGED
        MERGED --> PUT --> COPY
    end

    subgraph RAW_SCHEMA["Snowflake RAW Schema"]
        RAW_EPS["RAW.EPISODES\nvideo_id  VARCHAR PK\nraw_data  VARIANT\nloaded_at TIMESTAMP"]
        RAW_CHNL["RAW.CHANNELS\nchannel_id   VARCHAR PK\nchannel_name VARCHAR\ngenre        VARCHAR\nyoutube_url  VARCHAR"]
        COPY --> RAW_EPS
    end

    style SRC fill:#1e3a5f,color:#e2e8f0,stroke:#2d6a9f
    style LOCAL fill:#1e3a2e,color:#e2e8f0,stroke:#2d7a4f
    style MERGE fill:#3a2e1e,color:#e2e8f0,stroke:#7a5f2d
    style RAW_SCHEMA fill:#1a1a2e,color:#e2e8f0,stroke:#5555aa
```

---

## Diagram 3 — Transformation & Chunking Pipeline

```mermaid
flowchart TD
    RAW["RAW.EPISODES\n(VARIANT payload)"]

    subgraph STAGING_LAYER["STAGING Layer — SQL Views (no storage cost)"]
        STG1["STG_EPISODES\nraw_data:title::VARCHAR\nraw_data:publish_date::DATE\nraw_data:channel_id::VARCHAR\n22 typed columns total"]
        STG2["STG_SEGMENTS\nLATERAL FLATTEN(raw_data:transcript)\n1 row per WebVTT cue\n→ text, start_time, duration"]
        INT1["INT_EPISODES\nJOIN STG_EPISODES + RAW.CHANNELS\n+ TRANSCRIPT_QUALITY (word count check)\n+ ENGAGEMENT_RATE (views/day)"]
        INT2["INT_SEGMENTS\n+ YOUTUBE_TIMESTAMP_URL\nhttps://youtube.com/watch?v=ID&t=SECONDs\n+ WORD_COUNT per segment\n+ CUMULATIVE_SECONDS"]
        RAW --> STG1 & STG2
        STG1 --> INT1
        STG2 --> INT2
    end

    subgraph CHUNK_LOGIC["Chunking Logic — CUR_CHUNKS"]
        WINDOW["120-second sliding window\n15-second overlap\n(ensures context continuity\nacross chunk boundaries)"]
        CHUNK_ROW["One CUR_CHUNKS row:\nCHUNK_ID     VARCHAR PK\nVIDEO_ID     VARCHAR\nCHANNEL_NAME VARCHAR\nEPISODE_TITLE VARCHAR\nCHUNK_TEXT   VARCHAR  ← merged segment text\nCHUNK_WINDOW FLOAT    ← window number\nPUBLISH_DATE TIMESTAMP\nYOUTUBE_URL  VARCHAR  ← deep-link with &t=\nWORD_COUNT   INT\nTRANSCRIPT_QUALITY VARCHAR"]
        WINDOW --> CHUNK_ROW
    end

    INT1 & INT2 --> WINDOW

    STATS["Result: 13,807 chunks\n286 episodes · 25 channels\nAvg ~48 chunks/episode\nAvg ~180 words/chunk"]
    CHUNK_ROW --> STATS

    style STAGING_LAYER fill:#0f2027,color:#cdd6f4,stroke:#2c5364
    style CHUNK_LOGIC fill:#1a0f27,color:#cdd6f4,stroke:#5c3464
    STATS:::stat
    classDef stat fill:#0d3b2e,color:#7fffd4,stroke:#00cc88
```

---

## Diagram 4 — Semantic Enrichment Pipeline

```mermaid
flowchart TD
    CHUNKS["CUR_CHUNKS\n13,807 rows"]

    subgraph EMBED_PIPELINE["Embedding Generation"]
        ARCTIC["Snowflake Arctic-Embed-M\n768-dimensional dense vectors\nSNOWFLAKE.CORTEX.EMBED_TEXT_768"]
        EMBTBL["SEM_CHUNK_EMBEDDINGS\nCHUNK_ID VARCHAR\nEMBEDDING VECTOR(FLOAT, 768)\n13,807 vectors\n100% coverage"]
        CHUNKS --> ARCTIC --> EMBTBL
    end

    subgraph TOPIC_PIPELINE["Topic Extraction"]
        TLLM["Cortex LLM\nllama3.1-70b\nPrompt: Extract 2-5 topics\nfrom this podcast chunk"]
        TOPIC_TBL["SEM_CHUNK_TOPICS\nCHUNK_ID · TOPIC · CONFIDENCE\nBatch processed per episode"]
        CHUNKS --> TLLM --> TOPIC_TBL
    end

    subgraph NER_PIPELINE["Named Entity Recognition"]
        NLLM["Cortex LLM\nllama3.1-70b\nExtract: PERSON · ORG\nTECHNOLOGY · PRODUCT"]
        ENT_TBL["SEM_CHUNK_ENTITIES\nCHUNK_ID · ENTITY_NAME\nENTITY_TYPE · CONFIDENCE"]
        CHUNKS --> NLLM --> ENT_TBL
    end

    subgraph CLAIM_PIPELINE["Claim Extraction (Most Complex)"]
        direction TB
        CLLM["Cortex LLM\nllama3.1-70b\nStructured extraction prompt:\n- claim text\n- type (FACT/PREDICTION/OPINION/STATISTICAL)\n- sentiment\n- speaker name\n- speaker role (HOST/GUEST)"]
        ATTR["Two-Tier Speaker Attribution\n1. Metadata: parse episode title for guest names\n2. LLM inference: identify speaker from context\n→ Confidence: HIGH / MEDIUM / LOW"]
        CLAIM_TBL["SEM_CLAIMS\n84,260 claims extracted\n100% speaker attribution\nYOUTUBE_URL per claim\nVERIFICATION_STATUS"]
        CHUNKS --> CLLM --> ATTR --> CLAIM_TBL
    end

    subgraph PARTICIPANT_PIPELINE["Participant Extraction"]
        PTITLE["Title parsing\n'Sam Altman: Future of AI'\n→ GUEST: Sam Altman"]
        PLLM["LLM inference\nfrom description + transcript\nwhen title is ambiguous"]
        PART_TBL["SEM_EPISODE_PARTICIPANTS\n683 records\nPARTICIPANT_NAME · ROLE\nEXTRACTION_METHOD · CONFIDENCE"]
        CHUNKS --> PTITLE & PLLM --> PART_TBL
    end

    subgraph TEMPORAL_PIPELINE["Temporal Evolution Detection"]
        SIM["Cosine similarity scan\nCompare claim vectors\nacross time windows"]
        DRIFT["Drift classifier\nllama3.1-70b\nCONTRADICTED · ESCALATED\nCONFIRMED · SOFTENED · REVISED"]
        EVO_TBL["SEM_CLAIM_EVOLUTION\n823 evolution pairs\nORIGINAL_CLAIM_ID → EVOLVED_CLAIM_ID\nDRIFT_TYPE · SIMILARITY_SCORE\nTIME_DELTA_DAYS · ANALYSIS"]
        CLAIM_TBL --> SIM --> DRIFT --> EVO_TBL
    end

    style EMBED_PIPELINE fill:#1e3a5f,color:#cdd6f4,stroke:#2d6a9f
    style TOPIC_PIPELINE fill:#1e3a2e,color:#cdd6f4,stroke:#2d7a4f
    style NER_PIPELINE fill:#3a2e1e,color:#cdd6f4,stroke:#7a5f2d
    style CLAIM_PIPELINE fill:#3a1e2e,color:#cdd6f4,stroke:#7a2d5f
    style PARTICIPANT_PIPELINE fill:#1e2e3a,color:#cdd6f4,stroke:#2d5f7a
    style TEMPORAL_PIPELINE fill:#2e1e3a,color:#cdd6f4,stroke:#5f2d7a
```

---

## Diagram 5 — Hybrid Retrieval Architecture

```mermaid
flowchart LR
    QUERY["User Query\ne.g. 'What did experts say\nabout AI safety?'"]

    subgraph CORTEX_SEARCH_DETAIL["Cortex Search — Hybrid Retrieval"]
        BM25["BM25 Keyword Index\nTF-IDF sparse matching\nExact term overlap"]
        VEC_SEARCH["Vector Search\nANN over 13,807 embeddings\nArctic-embed-m 768-dim"]
        RERANK["Cortex Re-Ranker\nLLM-based cross-encoder\nBoosts semantic matches"]
        TOP8["Top-8 chunks returned\nwith EPISODE_TITLE\nCHANNEL_NAME · YOUTUBE_URL"]
        BM25 & VEC_SEARCH --> RERANK --> TOP8
    end

    subgraph NEO4J_DETAIL["Neo4j Graph Traversal"]
        PERSON_NODE["Person nodes\n(e.g. Sam Altman)"]
        MATCH_EP["MATCH (p:Person)-[:APPEARED_ON]->(e:Episode)\nRETURN e, count(*) as appearances"]
        MATCH_CLAIM["MATCH (p:Person)-[:MADE_CLAIM]->(c:Claim)\nWHERE c.topic CONTAINS 'AI safety'\nRETURN c ORDER BY c.date"]
        COAPP["CO_APPEARED_WITH edges\nShared episode appearances\ncounted + weighted"]
        PERSON_NODE --> MATCH_EP & MATCH_CLAIM & COAPP
    end

    subgraph SNOWFLAKE_SQL["Direct Snowflake SQL (Analytical Agents)"]
        CLAIM_SQL["SEM_CLAIMS query\nWHERE SPEAKER = 'Sam Altman'\nGROUP BY CLAIM_TYPE"]
        EVO_SQL["SEM_CLAIM_EVOLUTION JOIN\nFilter by DRIFT_TYPE = 'CONTRADICTED'\nORDER BY TIME_DELTA_DAYS"]
        INSIGHT_SQL["Insight aggregations\nCOUNT contradictions per channel\nTOP topics by claim density"]
    end

    QUERY --> CORTEX_SEARCH_DETAIL
    QUERY --> NEO4J_DETAIL
    QUERY --> SNOWFLAKE_SQL

    CORTEX_SEARCH_DETAIL --> CONTEXT["Retrieved Context\npassed to LLM"]
    NEO4J_DETAIL --> CONTEXT
    SNOWFLAKE_SQL --> CONTEXT

    style CORTEX_SEARCH_DETAIL fill:#1e3a5f,color:#cdd6f4,stroke:#2d6a9f
    style NEO4J_DETAIL fill:#1e3a2e,color:#cdd6f4,stroke:#00cc66
    style SNOWFLAKE_SQL fill:#1a1a2e,color:#cdd6f4,stroke:#5555cc
    CONTEXT:::ctx
    classDef ctx fill:#2e1a3a,color:#dda0dd,stroke:#9955cc,font-weight:bold
```

---

## Diagram 6 — LangGraph Multi-Agent Routing Flow

```mermaid
flowchart TD
    INPUT["User Query\n(via Streamlit Chat)"]

    GUARD["Input Guardrails\nLength check 3–500 chars\nInjection detection regex\nScope classification\nLanguage detection"]

    ROUTER["Router Agent\nllama3.1-8b\nClassify into 1 of 8 types\n87.5% accuracy (8b)\n93.8% accuracy (70b)"]

    INPUT --> GUARD
    GUARD -->|"PASS"| ROUTER
    GUARD -->|"FAIL"| BLOCKED["Blocked\nShow rejection message\nst.stop()"]

    ROUTER -->|"SEARCH"| SA["Search Agent\n\nCortex Search SEARCH_PREVIEW\nTop-8 hybrid results\nYouTube deep-links\n\nOutput: search_results[]"]

    ROUTER -->|"SUMMARIZE"| SUMM["Summarization Agent\n\nCortex Search → top-5 chunks\nllama3.1-70b synthesis\nCite sources inline\n\nOutput: summary str"]

    ROUTER -->|"GRAPH"| KG["Knowledge Graph Agent\n\nNeo4j Cypher query\nCO_APPEARED_WITH edges\nAppearance counts\n\nOutput: graph_results{}"]

    ROUTER -->|"TEMPORAL"| TEMP["Temporal Agent\n\nKeyword extract → llama3.1-8b\nSEM_CLAIM_EVOLUTION query\nSame-speaker pairs preferred\nllama3.1-70b narrative\n\nOutput: temporal_pairs[]"]

    ROUTER -->|"FACTCHECK"| FACT["Fact-Check Agent\n\nStage 1: Cortex LLM pre-filter\n  → VERIFIED / FALSE if confident\nStage 2: Brave Search MCP\n  → 5 web sources if uncertain\nStage 3: LLM synthesizes verdict\n\nOutput: factcheck_result{}"]

    ROUTER -->|"COMPARE"| COMP["Comparison Agent\n\nSEM_CLAIMS WHERE speaker IN (A, B)\nGroup claims by speaker\nllama3.1-70b comparison narrative\n\nOutput: comparison str + claims[]"]

    ROUTER -->|"RECOMMEND"| REC["Recommendation Agent\n\nSEM_EPISODE_PARTICIPANTS lookup\nTopic match on CUR_CHUNKS\nDedup by (title, channel)\nllama3.1-70b narrative\n\nOutput: recommendations[]"]

    ROUTER -->|"INSIGHT"| INS["Insight Agent\n\nSEM_CLAIMS GROUP BY channel\nCOUNT contradictions, predictions\nTop topics aggregation\nllama3.1-70b insight summary\n\nOutput: insight_summary str"]

    SA & SUMM & KG & TEMP & FACT & COMP & REC & INS --> RENDER

    RENDER["Response Renderer\napp.py\n\nFormat per query type\nSource cards · YouTube links\nFact-check verdict badge\nEvolution timeline cards\nComparison speaker groups"]

    RENDER --> DISCLAIMER["AI Disclaimer appended\n'Speaker attributions are AI-generated.\nVerify important claims at source.'"]

    DISCLAIMER --> OUT["Streamlit Chat Output"]

    style INPUT fill:#1e2a3a,color:#93c5fd,stroke:#3b82f6
    style GUARD fill:#3a1e1e,color:#fca5a5,stroke:#ef4444
    style BLOCKED fill:#3a1e1e,color:#fca5a5,stroke:#ef4444
    style ROUTER fill:#2e1e3a,color:#d8b4fe,stroke:#a855f7
    style SA fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style SUMM fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style KG fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style TEMP fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style FACT fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style COMP fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style REC fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style INS fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
    style RENDER fill:#1e2e3a,color:#93c5fd,stroke:#3b82f6
    style DISCLAIMER fill:#3a2e1e,color:#fcd34d,stroke:#f59e0b
    style OUT fill:#1e3a2e,color:#6ee7b7,stroke:#10b981
```

---

## Diagram 7 — Fact-Checking Data Flow (Two-Stage Pipeline)

```mermaid
flowchart TD
    CLAIM_IN["Input Claim\ne.g. 'GPT-5 was released in 2024'"]

    subgraph STAGE1["Stage 1 — LLM Pre-Filter  (Cortex Cortex · llama3.1-70b)"]
        CONF_CHECK{"LLM confidence\nhigh or low?"}
        HIGH_CONF["High confidence\n(training knowledge sufficient)"]
        LOW_CONF["Low confidence\n(needs web verification)"]
        CLAIM_IN --> CONF_CHECK
        CONF_CHECK -->|">= 0.85 confidence"| HIGH_CONF
        CONF_CHECK -->|"< 0.85 confidence"| LOW_CONF
    end

    subgraph STAGE1_OUT["Stage 1 Resolution (~60-70% of claims)"]
        VERIFIED1["VERIFIED\n(LLM only)"]
        FALSE1["FALSE\n(LLM only)"]
        HIGH_CONF --> VERIFIED1 & FALSE1
    end

    subgraph STAGE2["Stage 2 — Web Search  (MCP Brave Search API)"]
        MCP_CALL["MCP Web Search\nbrave_web_search tool\nQuery = claim text"]
        WEB_RESULTS["5 web results\ntitle + URL + snippet"]
        SYNTHESIS["Cortex LLM\nllama3.1-70b\nSynthesize verdict\nfrom web evidence"]
        LOW_CONF --> MCP_CALL --> WEB_RESULTS --> SYNTHESIS
    end

    subgraph STAGE2_OUT["Stage 2 Resolution (~30-40% of claims)"]
        VERIFIED2["VERIFIED\n+ source URLs"]
        DISPUTED["DISPUTED\nConflicting evidence"]
        OUTDATED["OUTDATED\nTrue then, false now"]
        UNVERIFIED["UNVERIFIED\nInsufficient evidence"]
        SYNTHESIS --> VERIFIED2 & DISPUTED & OUTDATED & UNVERIFIED
    end

    subgraph STORE["Store Result"]
        UPDATE["UPDATE SEM_CLAIMS\nSET VERIFICATION_STATUS = '...'\nEVIDENCE_SUMMARY = '...'\nEVIDENCE_URLS = [...]\nLAST_VERIFIED = NOW()"]
        VERIFIED1 & FALSE1 & VERIFIED2 & DISPUTED & OUTDATED & UNVERIFIED --> UPDATE
    end

    subgraph UI_RENDER["UI Rendering"]
        CARD["Fact-Check Card\n[VERDICT BADGE]\nClaim text\nEvidence summary\nSource links"]
        UPDATE --> CARD
    end

    style STAGE1 fill:#1e2a3a,color:#cdd6f4,stroke:#3b82f6
    style STAGE1_OUT fill:#1a2e1a,color:#cdd6f4,stroke:#10b981
    style STAGE2 fill:#2a1e3a,color:#cdd6f4,stroke:#8b5cf6
    style STAGE2_OUT fill:#1a2e1a,color:#cdd6f4,stroke:#10b981
    style STORE fill:#2a2a1e,color:#cdd6f4,stroke:#f59e0b
    style UI_RENDER fill:#1e2a2a,color:#cdd6f4,stroke:#06b6d4
```

---

## Diagram 8 — Snowflake 4-Layer Schema Architecture

```mermaid
flowchart LR
    subgraph RAW["RAW Layer\n(Source of Truth)"]
        R1["EPISODES\nvideo_id PK\nraw_data VARIANT\nloaded_at TIMESTAMP\n\n286 rows"]
        R2["CHANNELS\nchannel_id PK\nchannel_name\ngenre\n\n25 rows"]
    end

    subgraph STAGING["STAGING Layer\n(Views — zero storage)"]
        S1["STG_EPISODES\nFlattened VARIANT\n22 typed columns"]
        S2["STG_SEGMENTS\nFLATTEN transcript\n1 row per cue"]
        S3["INT_EPISODES\n+ quality score\n+ engagement rate"]
        S4["INT_SEGMENTS\n+ timestamp URL\n+ word count"]
        R1 --> S1 --> S3
        R1 --> S2 --> S4
        R2 --> S3
    end

    subgraph CURATED["CURATED Layer\n(Materialized)"]
        C1["CUR_CHUNKS\nchunk_id PK\nvideo_id FK\nchannel_name\nepisode_title\nchunk_text\nchunk_window\npublish_date\nyoutube_url\nword_count\n\n13,807 rows"]
        S3 & S4 --> C1
    end

    subgraph SEMANTIC["SEMANTIC Layer\n(AI-Enriched)"]
        SEM1["SEM_CHUNK_EMBEDDINGS\nchunk_id FK\nembedding VECTOR(768)\n\n13,807 rows · 100%"]
        SEM2["SEM_CHUNK_TOPICS\nchunk_id FK\ntopic\nconfidence"]
        SEM3["SEM_CHUNK_ENTITIES\nchunk_id FK\nentity_name\nentity_type"]
        SEM4["SEM_EPISODE_SUMMARIES\nvideo_id FK\nsummary_text"]
        SEM5["SEM_CLAIMS\nclaim_id PK\nchunk_id FK\nclaim_text\nspeaker\nclaim_type\nverification_status\n\n84,260 rows"]
        SEM6["SEM_EPISODE_PARTICIPANTS\nvideo_id FK\nparticipant_name\nrole HOST/GUEST\n\n683 rows"]
        SEM7["SEM_CLAIM_EVOLUTION\nevolution_id PK\noriginal_claim_id FK\nevolved_claim_id FK\ndrift_type\nsimilarity_score\ntime_delta_days\n\n823 rows"]
        CS["PODCASTIQ_SEARCH\nCortex Search Service\nHybrid vector + BM25\nover CUR_CHUNKS"]
        C1 --> SEM1 & SEM2 & SEM3 & SEM4
        C1 --> SEM5 --> SEM6
        SEM5 --> SEM7
        SEM1 --> CS
    end

    style RAW fill:#1e1e3a,color:#cdd6f4,stroke:#4040aa
    style STAGING fill:#1e2e1e,color:#cdd6f4,stroke:#40aa40
    style CURATED fill:#2e1e1e,color:#cdd6f4,stroke:#aa4040
    style SEMANTIC fill:#1e2e2e,color:#cdd6f4,stroke:#40aaaa
```

---

## Diagram 9 — Neo4j Knowledge Graph Schema

```mermaid
flowchart LR
    subgraph NODES["Node Types  (88,823 total)"]
        PN["Person\nname, type\ne.g. Sam Altman"]
        EN["Episode\nvideo_id, title\nchannel, date"]
        TN["Topic\nname\ne.g. AI Safety"]
        CN["Channel\nname, genre\ne.g. Lex Fridman"]
        CLN["Claim\ntext, type\ndate, speaker"]
        ORG["Organization\nname\ne.g. OpenAI"]
    end

    subgraph EDGES["Edge Types  (253,740 total)"]
        E1["APPEARED_ON\nPerson → Episode\nrole: HOST/GUEST"]
        E2["HOSTED_BY\nEpisode → Channel"]
        E3["MADE_CLAIM\nPerson → Claim\nconfidence"]
        E4["DISCUSSED\nEpisode → Topic\nfrequency"]
        E5["CO_APPEARED_WITH\nPerson ↔ Person\ncount, episodes[]"]
        E6["EVOLVED_FROM\nClaim → Claim\ndrift_type"]
        E7["AFFILIATED_WITH\nPerson → Organization"]
        E8["RELATED_TO\nTopic ↔ Topic\nco_occurrence"]
    end

    PN -->|"APPEARED_ON"| EN
    EN -->|"HOSTED_BY"| CN
    PN -->|"MADE_CLAIM"| CLN
    EN -->|"DISCUSSED"| TN
    PN -->|"CO_APPEARED_WITH"| PN
    CLN -->|"EVOLVED_FROM"| CLN
    PN -->|"AFFILIATED_WITH"| ORG
    TN -->|"RELATED_TO"| TN

    subgraph CYPHER["Example Cypher Queries"]
        CQ1["Guest Network Query:\nMATCH (p:Person {name:'Sam Altman'})\n      -[:CO_APPEARED_WITH]->(co)\nRETURN co.name, rel.count\nORDER BY rel.count DESC"]
        CQ2["Claim Evolution Query:\nMATCH (c1:Claim)-[e:EVOLVED_FROM]->(c2)\nWHERE e.drift_type = 'CONTRADICTED'\nRETURN c1, c2, e.time_delta_days"]
    end

    style NODES fill:#1e3a2e,color:#cdd6f4,stroke:#00cc66
    style EDGES fill:#1e2e3a,color:#cdd6f4,stroke:#0066cc
    style CYPHER fill:#2e2e1e,color:#fcd34d,stroke:#cc9900
```

---

## Diagram 10 — Evaluation Framework

```mermaid
flowchart TD
    subgraph EVAL_SUITE["Evaluation Suite  (scripts/evaluation/)"]
        RE["router_eval.py\n48 queries × 8 types\nllama3.1-8b: 87.5%\nllama3.1-70b: 93.8%\nAblation delta: +6.2%"]
        RTE["retrieval_eval.py\n20 test queries\nLLM relevance judge\nP@1: 0.700\nP@3: 0.550\nP@8: 0.419\nMRR: 0.800"]
        GE["generation_eval.py\n10 SUMMARIZE queries\nROUGE-1 / ROUGE-2 / ROUGE-L\nBERTScore F1\nLLM-as-judge:\n  Faithfulness 1–5\n  Relevance 1–5\n  Groundedness 1–5"]
        LE["latency_eval.py\n8 agent types × 3 runs\nMean + p95 per agent\nOverall p95 target < 5s"]
        CE["cost_eval.py\nStatic token budgets\n× Cortex pricing\nAvg: $0.0012/query\nProjected: $1.19/1k"]
        DK["domain_kpis.py\n7/7 checks PASS\n13,807 chunks ✓\n84,260 claims ✓\n823 evolution pairs ✓\n100% embedding coverage ✓\n100% speaker attribution ✓\n100% URL validity ✓"]
        RA["run_all.py\nMaster runner\n--quick flag\nConsolidated report\neval_summary.json"]
    end

    RE & RTE & GE & LE & CE & DK --> RA
    RA --> REPORT["eval_summary.json\nAll metrics in one file\nPresentation-ready numbers"]

    style EVAL_SUITE fill:#1a1a2e,color:#cdd6f4,stroke:#5555aa
    REPORT:::rep
    classDef rep fill:#0d3b2e,color:#7fffd4,stroke:#00cc88,font-weight:bold
```

---

## Quick Reference — Data Volumes

| Stage | Table / Object | Rows / Size |
|-------|---------------|-------------|
| Extraction | YouTube transcripts | 286 episodes · 25 channels · 6 genres |
| Raw | `RAW.EPISODES` | 286 VARIANT rows |
| Curated | `CUR_CHUNKS` | **13,807 chunks** (120s windows) |
| Embeddings | `SEM_CHUNK_EMBEDDINGS` | **13,807 × 768-dim vectors** |
| Claims | `SEM_CLAIMS` | **84,260 claims** (100% speaker-attributed) |
| Evolution | `SEM_CLAIM_EVOLUTION` | **823 pairs** (CONTRADICTED · ESCALATED · CONFIRMED · SOFTENED · REVISED) |
| Participants | `SEM_EPISODE_PARTICIPANTS` | 683 host/guest records |
| Knowledge Graph | Neo4j | **88,823 nodes · 253,740 relationships** |
| Search Index | Cortex Search `PODCASTIQ_SEARCH` | Hybrid BM25 + vector over 13,807 chunks |
| Temporal coverage | Jan 2022 → Feb 2026 | **44 months** |

## Quick Reference — Model Usage

| Agent / Step | Model | Purpose |
|---|---|---|
| Router | `llama3.1-8b` | Query classification (8 types) |
| Embedding | `Arctic-embed-m` | 768-dim dense vectors |
| Retrieval re-ranking | Cortex Search built-in | Hybrid BM25 + vector re-rank |
| Summarization | `llama3.1-70b` | Synthesis from retrieved chunks |
| Comparison | `llama3.1-70b` | Cross-speaker claim analysis |
| Temporal | `llama3.1-70b` | Evolution narrative generation |
| Fact-check (Stage 1) | `llama3.1-70b` | Pre-filter from training knowledge |
| Fact-check (Stage 2) | Brave Search MCP + `llama3.1-70b` | Web retrieval + verdict synthesis |
| Insight | `llama3.1-70b` | Meta-analysis narrative |
| Claim extraction | `llama3.1-70b` | Structured claim + speaker extraction |
| LLM judge (eval) | `llama3.1-70b` | Faithfulness / Relevance / Groundedness |
