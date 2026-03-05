# PodcastIQ - Week 1 Class Update
### Data Extraction & Profiling Progress
**Date:** February 21, 2026

---

## 1. The Extraction Challenge: IP Blocking

### What Happened

Our first attempt at extracting YouTube transcripts **completely failed** - 0 out of 250 episodes extracted.

We used the `youtube-transcript-api` Python library, which is the standard way to pull YouTube captions programmatically. On our very first run (Feb 20, 12:41 AM), every single request came back with this error:

```
YouTube is blocking requests from your IP. This is most likely caused by:
- You have done too many requests and your IP has been blocked by YouTube
- You are doing requests from an IP belonging to a cloud provider
```

**The timeline of failure:**

| Attempt | Time | Method | Result |
|---------|------|--------|--------|
| 1 | 12:41 AM | `youtube-transcript-api` (raw) | 0/20 - **IP blocked** |
| 2 | 1:27 AM | `youtube-transcript-api` + browser cookies | 0/20 - **Still blocked** |
| 3 | 1:32 AM | First `yt-dlp` attempt (wrong flags) | 0/20 - **"Requested format not available"** |
| 4 | 1:33 AM | `yt-dlp` without `--impersonate` | 0/20 - **All failed** |
| 5 | 11:22 AM | `yt-dlp` + `--impersonate chrome` + cookies | **10/10 SUCCESS** |

We went from 0% success to 100% success by switching tools and approach.

```
EXTRACTION ATTEMPTS TIMELINE (Feb 20, 2026)
════════════════════════════════════════════════════════════════════════

12:41 AM   youtube-transcript-api (raw)              0/20 BLOCKED
  │        ┌──────────────────────────────────┐
  │        │ "YouTube is blocking requests    │
  │        │  from your IP"                   │
  │        └──────────────────────────────────┘
  │
 1:27 AM   youtube-transcript-api + cookies          0/20 BLOCKED
  │        ┌──────────────────────────────────┐
  │        │ Same IP block error              │
  │        │ Cookies alone not enough         │
  │        └──────────────────────────────────┘
  │
 1:32 AM   yt-dlp (wrong flags)                      0/20 FAILED
  │        ┌──────────────────────────────────┐
  │        │ "Requested format is not         │
  │        │  available"                      │
  │        └──────────────────────────────────┘
  │
 1:33 AM   yt-dlp (no --impersonate)                 0/20 FAILED
  │        ┌──────────────────────────────────┐
  │        │ All 20 videos failed             │
  │        │ Still detected as bot            │
  │        └──────────────────────────────────┘
  │
  │        ~~~ researched yt-dlp docs & TLS fingerprinting ~~~
  │
11:22 AM   yt-dlp + --impersonate chrome + cookies   10/10 SUCCESS
           ┌──────────────────────────────────┐
           │ Full browser impersonation       │
           │ 250/250 episodes extracted       │
           │ across 25 channels in ~17 min    │
           └──────────────────────────────────┘
```

---

## 2. How We Solved It: Three Methods Tried

### Method 1: `youtube-transcript-api` (FAILED)
- Standard Python library for fetching YouTube captions
- Makes direct HTTP requests to YouTube's internal transcript API
- **Problem:** YouTube detects these as bot requests and blocks the IP
- Even with rate limiting (0.3s delay between requests), every request was blocked

### Method 2: `youtube-transcript-api` + Browser Cookies (FAILED)
- Exported our real browser cookies from Chrome (`www.youtube.com_cookies.txt`)
- Passed cookies to the API to look like an authenticated browser session
- **Problem:** The library's request pattern is still detectable regardless of cookies
- YouTube's anti-bot system looks at more than just cookies - it checks request headers, TLS fingerprinting, etc.

### Method 3: `yt-dlp` + `--impersonate chrome` + Cookies (SUCCESS)
- `yt-dlp` is a powerful media downloader with built-in browser impersonation
- Key flags that made it work:
  - `--impersonate chrome` - mimics Chrome's exact TLS fingerprint, HTTP headers, and request patterns
  - `--cookies` - uses real browser session cookies
  - `--write-auto-sub --write-sub` - downloads subtitle/caption files (VTT format)
  - `--skip-download` - only grabs captions, not the video itself
  - `--ignore-no-formats-error` - handles edge cases gracefully
- We then parse the downloaded `.vtt` (WebVTT) subtitle files into structured JSON segments
- **Result:** 250/250 episodes extracted successfully across 25 channels

### Why `yt-dlp` Worked Where the Python Library Didn't
- `yt-dlp` performs full **TLS fingerprint impersonation** - it doesn't just set User-Agent headers, it actually mimics Chrome's entire TLS handshake (cipher suites, extensions, ALPN protocols)
- YouTube's anti-bot system uses **JA3/JA4 fingerprinting** to detect non-browser clients. Python's `requests` library has a completely different TLS fingerprint than Chrome, so YouTube blocks it instantly
- The library makes requests to YouTube's undocumented internal API, while `yt-dlp` uses the same endpoints a real browser would use

---

## 3. Final Extraction Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        PODCASTIQ EXTRACTION PIPELINE                        │
│                     scripts/channel_extraction.py                           │
└─────────────────────────────────────────────────────────────────────────────┘

  INPUT                                                              OUTPUT
  channels.json                                                      data/raw/
  (25 channels)                                                      (500 JSON files)

  ┌──────────────────┐          ┌──────────────────────────────┐
  │  CHANNEL CONFIG   │          │      YOUTUBE DATA API v3     │
  │                   │          │      (official, API key)     │
  │  channel_id ──────┼────┐     │                              │
  │  name             │    │     │  channels().list ──────────┐ │
  │  genre            │    ├────>│  playlistItems().list      │ │
  │  target_episodes  │    │     │  videos().list             │ │
  │  handle           │    │     │     (part=snippet,         │ │
  └──────────────────┘    │     │      contentDetails,       │ │
                           │     │      statistics)           │ │
                           │     └──────────┬─────────────────┘ │
                           │                │                    │
                           │                v                    │
                           │     ┌──────────────────────────┐   │
                           │     │    VIDEO METADATA         │   │
                           │     │                           │   │
                           │     │  title, description       │   │
                           │     │  channel_id, channel_name │   │
                           │     │  publish_date             │   │
                           │     │  duration_iso (PT1H30M)   │   │
                           │     │  duration_minutes (90.0)  │   │
                           │     │  view_count, like_count   │   │
                           │     │  video_url                │   │
                           │     └────────────┬──────────────┘   │
                           │                  │                  │
                           │                  v                  │
                           │     ┌──────────────────────────┐   │
                           │     │ {video_id}_metadata.json  │   │
                           │     └──────────────────────────┘   │
                           │                                     │
  ┌──────────────────┐     │     ┌──────────────────────────────┐
  │  ANTI-BOT BYPASS  │     │     │         yt-dlp               │
  │                   │     │     │   (browser impersonation)    │
  │  --impersonate    │     │     │                              │
  │    chrome         │     ├────>│  --write-auto-sub            │
  │  --cookies        │     │     │  --write-sub                 │
  │    cookies.txt    │     │     │  --sub-lang en               │
  │                   │     │     │  --skip-download             │
  │  TLS fingerprint  │     │     │  --ignore-no-formats-error   │
  │  mimics Chrome    │     │     │                              │
  └──────────────────┘     │     └──────────┬─────────────────┘ │
                           │                │                    │
                           │                v                    │
                           │     ┌──────────────────────────┐   │
                           │     │   RAW VTT SUBTITLES       │   │
                           │     │                           │   │
                           │     │  00:01:23.456 --> 00:01:27│   │
                           │     │  "He said very specifi..."│   │
                           │     └────────────┬──────────────┘   │
                           │                  │                  │
                           │                  v                  │
                           │     ┌──────────────────────────┐   │
                           │     │   parse_vtt_to_segments() │   │
                           │     │                           │   │
                           │     │  VTT ──> JSON array       │   │
                           │     │  [{ text, start,          │   │
                           │     │     duration }, ...]       │   │
                           │     └────────────┬──────────────┘   │
                           │                  │                  │
                           │                  v                  │
                           │     ┌──────────────────────────┐   │
                           │     │{video_id}_transcript.json │   │
                           │     └──────────────────────────┘   │
                           │                                     │
                           │     ┌──────────────────────────────┐
                           │     │     RESUME & PROGRESS         │
                           └────>│                               │
                                 │  extraction_progress.json     │
                                 │  _channel_summary.json        │
                                 │  _extraction_summary.json     │
                                 │                               │
                                 │  - Tracks downloaded IDs      │
                                 │  - Safe to re-run (idempotent)│
                                 │  - Resumes from last success  │
                                 └──────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │                    OUTPUT: data/raw/                         │
  ├─────────────────────────────────────────────────────────────┤
  │                                                             │
  │  data/raw/                                                  │
  │  ├── Lex_Fridman_Podcast/                                   │
  │  │   ├── f_lRdkH_QoY_metadata.json     ← video metadata    │
  │  │   ├── f_lRdkH_QoY_transcript.json   ← caption segments  │
  │  │   ├── tYrdMjVXyNg_metadata.json                         │
  │  │   ├── tYrdMjVXyNg_transcript.json                       │
  │  │   └── _channel_summary.json         ← extraction stats  │
  │  ├── All-In_Podcast/                                        │
  │  │   ├── ...                                                │
  │  ├── Huberman_Lab/                                          │
  │  │   ├── ...                                                │
  │  └── ... (25 channel folders)                               │
  │                                                             │
  │  Total: 250 episodes x 2 files = 500 JSON files            │
  └─────────────────────────────────────────────────────────────┘
```

**Two-API approach:**
1. **YouTube Data API v3** (official, with API key) - for metadata (title, views, duration, etc.)
2. **yt-dlp** (browser impersonation) - for transcript/caption extraction

This separation is important because:
- Metadata comes from the official API (reliable, structured, rate-limited to 10,000 units/day)
- Transcripts need browser impersonation to bypass IP blocking
- If one fails, the other's data is preserved

---

## 4. Data Profiling: Why We Did TWO Types

We performed two complementary types of profiling, each serving a different purpose:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PODCASTIQ PROFILING PIPELINE                          │
│                  Two complementary profiling approaches                     │
└─────────────────────────────────────────────────────────────────────────────┘

                         data/raw/ (500 JSON files)
                                   │
                    ┌──────────────┴──────────────┐
                    │                              │
                    v                              v
  ┌─────────────────────────────┐  ┌──────────────────────────────────┐
  │   PROFILING TYPE 1           │  │   PROFILING TYPE 2                │
  │   ydata-profiling            │  │   Custom Python Profiler          │
  │   (Statistical EDA)          │  │   (Domain-Specific Quality)       │
  │                              │  │                                   │
  │   scripts/advanced_profile.py│  │   profiling/profile_raw_data.py   │
  ├──────────────────────────────┤  ├───────────────────────────────────┤
  │                              │  │                                   │
  │   WHAT IT DOES:              │  │   WHAT IT DOES:                   │
  │                              │  │                                   │
  │   JSON ──> pandas DataFrame  │  │   JSON ──> EpisodeProfile objects │
  │         ──> ProfileReport()  │  │         ──> quality scoring       │
  │         ──> HTML report      │  │         ──> accept/reject logic   │
  │                              │  │         ──> ASCII report          │
  │   METRICS:                   │  │                                   │
  │   ┌────────────────────────┐ │  │   METRICS:                        │
  │   │ Column distributions   │ │  │   ┌─────────────────────────────┐ │
  │   │ (histograms, box plots)│ │  │   │ Coverage % (transcript vs  │ │
  │   │                        │ │  │   │   video duration)           │ │
  │   │ Correlation matrix     │ │  │   │                             │ │
  │   │ (views vs duration?)   │ │  │   │ Quality Score (0.0 - 1.0)  │ │
  │   │                        │ │  │   │   40% coverage              │ │
  │   │ Missing value analysis │ │  │   │   20% artifact ratio        │ │
  │   │ (null rates per field) │ │  │   │   20% words-per-minute      │ │
  │   │                        │ │  │   │   10% timestamp gaps        │ │
  │   │ Duplicate detection    │ │  │   │   10% empty segments        │ │
  │   │ (duplicate video_ids?) │ │  │   │                             │ │
  │   │                        │ │  │   │ Artifact detection          │ │
  │   │ Type inference         │ │  │   │   [Music] [Applause] etc.   │ │
  │   │ (dates, numbers, text) │ │  │   │                             │ │
  │   │                        │ │  │   │ Timestamp gap detection     │ │
  │   │ Alerts                 │ │  │   │   (gaps > 30s between segs) │ │
  │   │ (skewness, zeros,     │ │  │   │                             │ │
  │   │  high cardinality)     │ │  │   │ Accept / Reject decision   │ │
  │   └────────────────────────┘ │  │   │   HIGH   > 0.7  ──> ACCEPT │ │
  │                              │  │   │   MEDIUM 0.5-0.7 ──> ACCEPT│ │
  │                              │  │   │   LOW    < 0.5  ──> REJECT │ │
  │                              │  │   └─────────────────────────────┘ │
  │   ANSWERS:                   │  │                                   │
  │   "Is our data              │  │   ANSWERS:                        │
  │    well-formed?"            │  │   "Is our data good               │
  │                              │  │    enough to use?"                │
  │   (statistical perspective)  │  │   (domain/quality perspective)    │
  ├──────────────────────────────┤  ├───────────────────────────────────┤
  │                              │  │                                   │
  │   OUTPUT:                    │  │   OUTPUT:                         │
  │   reports/                   │  │   reports/                        │
  │   transcript_data_profile    │  │   extraction_profile_report       │
  │   .html                      │  │   .txt                            │
  │                              │  │                                   │
  │   Interactive HTML report    │  │   ASCII text report               │
  │   (open in browser)          │  │   (terminal / version control)    │
  └──────────────┬───────────────┘  └──────────────┬────────────────────┘
                 │                                  │
                 └──────────────┬───────────────────┘
                                │
                                v
                 ┌──────────────────────────────┐
                 │      GATE: LOAD DECISION      │
                 │                               │
                 │  ydata  says: data is clean?   │
                 │  custom says: quality >= 0.5?  │
                 │                               │
                 │  BOTH PASS ──> proceed to     │
                 │  Snowflake loading (Step 3-4)  │
                 │                               │
                 │  EITHER FAILS ──> investigate  │
                 │  & fix before loading          │
                 └──────────────────────────────┘
```

### Why Two Profilers? (The Key Distinction)

| Aspect | ydata-profiling | Custom Profiler |
|--------|----------------|-----------------|
| **Type** | Generic statistical EDA | Domain-specific quality gate |
| **Input** | Any pandas DataFrame | Podcast transcript JSON |
| **Output** | Interactive HTML (shareable) | ASCII text (terminal/git) |
| **Answers** | "Is our data well-formed?" | "Is our data good enough to use?" |
| **Example** | "view_count has 0.0% nulls" | "99.7% transcript coverage" |
| **Example** | "duration_min is right-skewed" | "0.4% segments have [Music] artifacts" |
| **Example** | "publish_date parsed correctly" | "Quality score: 0.719 - 1.000" |
| **Can it score quality?** | No | Yes (composite 0-1 score) |
| **Can it accept/reject?** | No | Yes (threshold-based gating) |
| **Industry standard?** | Yes (EDA best practice) | No (custom to our domain) |

**Bottom line:** ydata tells us the data *looks right*. Our custom profiler tells us the data *is right for our use case*. Together they form a quality gate before we load anything into Snowflake.

---

## 5. Profiling Results Summary

```
============================================================
  PodcastIQ Extraction Profile Report
  Date: 2026-02-21
============================================================

  Total videos extracted:       250
  Successful transcripts:       250
  Failed extractions:             0 (0.0%)

  Quality Distribution:
  HIGH (>0.7):      250 (100.0%)
  MEDIUM (0.5-0.7):   0 (0.0%)
  LOW (<0.5):         0 (0.0%)

  Accepted for loading:         250
  Rejected:                       0

  Avg segments per episode:     4,736
  Avg words per episode:       48,936
  Total words in dataset:     12,234,052
  Total hours of content:       388.1 hrs

  Artifact rate:                0.4% of segments
  Empty segment rate:           0.0% of segments
  Timestamp gap rate:           0.4% of episodes

  Channel Coverage:           25/25
  Genre Coverage:             6/6
============================================================
```

**Key takeaways:**
- **100% extraction success rate** - all 250 target episodes have transcripts
- **100% HIGH quality** - every episode scores above 0.7 on our composite quality metric
- **12.2 million words** across 388 hours of podcast content
- **Minimal noise** - only 0.4% of segments contain artifacts like [Music]
- **Full coverage** - all 25 channels and all 6 genres represented
- **0 episodes rejected** - all 250 are accepted for loading into Snowflake

---

## 6. Genre & Channel Coverage

| Genre | Episodes | Channels |
|-------|----------|----------|
| Technology & AI | 70 | Lex Fridman, All-In, No Priors, Acquired, a16z, Hard Fork, Cognitive Revolution |
| Business & Entrepreneurship | 60 | Tim Ferriss, My First Million, Lenny's, Y Combinator, Knowledge Project, How I Built This |
| Education & Self-Improvement | 50 | Impact Theory, Ali Abdaal, Diary of a CEO, Founders, Modern Wisdom |
| Science & Health | 40 | Huberman Lab, Peter Attia, FoundMyFitness, StarTalk |
| Startup & VC | 20 | 20VC, Masters of Scale |
| Cross-Disciplinary | 10 | Joe Rogan Experience |

---

## 7. What's Next (Week 2)

Now that extraction and profiling are complete, we move to **Steps 3-6**:

1. **Stage** - PUT JSON files to Snowflake internal stage
2. **Load** - COPY INTO raw tables (VARIANT columns for JSON)
3. **Clean** - dbt staging models (parse JSON, remove noise, fix text)
4. **Structure** - dbt intermediate models (join metadata + transcripts, derive fields)

The Snowflake loader script (`scripts/snowflake_loader.py`) is already built and ready to run.
