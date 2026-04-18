"""
GPT-4o Response Validator

Checks the llama-generated answer against the retrieved source chunks
and returns a confidence score + verdict for display in the UI.
"""

import os
import json
from dotenv import load_dotenv
load_dotenv()

VALIDATE_PROMPT = """You are an independent quality checker for an AI podcast intelligence system.

A user asked a question. An AI assistant answered it using podcast transcript excerpts (shown below).
Your job is to check whether the answer is faithful to those excerpts.

User Question: {query}

Source Excerpts (what the AI was given):
{context}

AI-Generated Answer:
{answer}

Evaluate the answer and respond with ONLY valid JSON:
{{
  "confidence": <0-100>,
  "verdict": "<one of: VERIFIED | MOSTLY_ACCURATE | PARTIALLY_ACCURATE | UNVERIFIED>",
  "flag": "<null or one short sentence describing the main concern if confidence < 70>"
}}

Scoring guide:
- VERIFIED (85-100): All claims are directly supported by the excerpts
- MOSTLY_ACCURATE (65-84): Most claims supported, minor extrapolations
- PARTIALLY_ACCURATE (40-64): Some claims supported, some go beyond the excerpts
- UNVERIFIED (0-39): Claims largely unsupported or contradict the excerpts
"""

AGENTS_TO_VALIDATE = {"SUMMARIZE", "SEARCH", "FACTCHECK", "COMPARE", "TEMPORAL"}


def validate_response(query: str, answer: str, search_results: list, query_type: str) -> dict | None:
    """
    Call GPT-4o to validate the llama-generated answer.
    Returns a dict with confidence, verdict, flag — or None if validation is skipped.
    """
    if query_type not in AGENTS_TO_VALIDATE:
        return None

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.strip().startswith("#"):
        return None

    # Build context from retrieved chunks (same as what llama saw)
    context_parts = []
    for i, r in enumerate(search_results[:5], 1):
        title = r.get("episode_title") or r.get("EPISODE_TITLE", "")
        text  = r.get("chunk_text")    or r.get("CHUNK_TEXT", "")
        context_parts.append(f"[{i}] {title}\n{str(text)[:400]}")
    context = "\n\n".join(context_parts) if context_parts else "No source excerpts available."

    prompt = VALIDATE_PROMPT.format(
        query=query,
        context=context,
        answer=answer[:1200],
    )

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=150,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or ""
        result = json.loads(raw)
        return {
            "confidence": int(result.get("confidence", 0)),
            "verdict":    str(result.get("verdict", "UNVERIFIED")),
            "flag":       result.get("flag"),
        }
    except Exception as e:
        return {"confidence": None, "verdict": "ERROR", "flag": str(e)[:80]}
