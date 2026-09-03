"""Research the latest news/trends for the day's subtopic and draft the post.

This is the single "intelligence" call: Claude runs server-side web searches,
synthesises what is new, writes the post in your voice, and returns structured
JSON (post text, image prompt, hashtags, sources).
"""
from __future__ import annotations

import argparse
import json
import os
import re

import anthropic

from .common import out_dir, read_json, load_config, require_env, write_json

# A newer dated web_search tool exists (e.g. web_search_20260209); this stable
# version is broadly supported. Bump it if the docs recommend a newer one.
#
# max_uses is the main cost dial: every search drops its results into the
# context, and the whole context is resent on each turn of the tool loop, so
# the cost of an extra search compounds. Three is enough for one post.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}

DEFAULT_MODEL = "claude-sonnet-5"

DEFAULT_MAX_CHARS = 1200


def max_chars(cfg: dict) -> int:
    return int(cfg.get("voice", {}).get("max_chars") or DEFAULT_MAX_CHARS)


def build_system(cfg: dict) -> str:
    voice = cfg.get("voice", {})
    image = cfg.get("image", {})
    guidelines = "\n".join(f"- {g}" for g in voice.get("guidelines", []))
    emojis = "You may use tasteful emojis." if voice.get("use_emojis") else "Do not use emojis."
    n_tags = voice.get("hashtag_count", 4)
    limit = max_chars(cfg)
    return f"""You research and write a single LinkedIn post.

WHAT THIS POST IS FOR
{cfg.get('mission', '').strip()}

AUTHOR VOICE
{voice.get('author_context', '').strip()}

AUDIENCE
{voice.get('audience', '').strip()}

PROCESS
1. Use web search to find genuinely RECENT news, releases, or trends (prefer the
   last 30 days) for the given topic and subtopic. Run several searches. Prefer
   primary sources (official blogs, release notes, docs, reputable reporting).
2. Note 2 to 4 concrete developments worth mentioning, with what changed and why
   it matters. Only use figures/claims you actually found; never invent numbers.
3. Choose the honest angle. Ask what a well-informed reader would probably
   believe about this subject and whether the evidence supports it. If there is a
   real gap, that gap is the post. If there is not, do not manufacture one:
   report what genuinely changed, or explain a better way to do the job. All
   three are good posts; a forced contrarian take is not.
4. Write ONE LinkedIn post in the author's voice.

POST RULES
{guidelines}
- {emojis}
- Append exactly {n_tags} relevant hashtags.
- HARD LIMIT: the post must be at most {limit} characters, hashtags included.
  Count before you answer and cut until it fits. Going over is a failed post.

IMAGE
Also produce an image prompt for an accompanying illustration in this style:
{image.get('style', '').strip()}

OUTPUT
Respond with ONLY a single JSON object, no markdown fences, no preamble.
The "commentary" must be plain text ready to paste into LinkedIn: no markup of
any kind, no <cite> tags, no citation markers, no reference numbers. Put the
sources in the "sources" field instead.
{{
  "commentary": "the full post text including hashtags on their own final line, at most {limit} characters",
  "image_prompt": "a vivid prompt for the illustration, no text in the image",
  "hashtags": ["#Example", "..."],
  "sources": [{{"title": "...", "url": "..."}}]
}}"""

# Claude's server-side web search wraps quoted material in <cite index="...">
# tags. They must never reach LinkedIn, which would render them literally.
CITE_TAG = re.compile(r"</?cite\b[^>]*>", re.IGNORECASE)


def strip_markup(text: str) -> str:
    """Remove citation tags and tidy the whitespace they leave behind."""
    text = CITE_TAG.sub("", text)
    # Collapse spaces left mid-sentence, but keep paragraph breaks intact.
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip()


def extract_json(text: str) -> dict:
    text = text.strip()
    # Strip code fences if present.
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost brace pair.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise SystemExit("Model did not return parseable JSON. Raw output:\n" + text[:2000])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    cfg = load_config()
    selection = read_json(d / "selection.json")
    model = os.environ.get("CLAUDE_MODEL") or DEFAULT_MODEL

    client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    user_prompt = (
        f"Topic: {selection['topic']}\n"
        f"Subtopic: {selection['subtopic']}\n\n"
        "Research the latest and write the post now."
    )

    # Headroom matters more than it looks: Sonnet 5 thinks by default, and a
    # thinking pass of ~1300 tokens plus the JSON left nothing under the old
    # 2500 ceiling - the model was truncated before it emitted any text. Only
    # tokens actually generated are billed, so a high ceiling is free insurance.
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=build_system(cfg),
        messages=[{"role": "user", "content": user_prompt}],
        tools=[WEB_SEARCH_TOOL],
    )

    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    if not text.strip():
        raise SystemExit(
            "Model returned no text block. "
            f"stop_reason={resp.stop_reason}, blocks={[b.type for b in resp.content]}, "
            f"usage={resp.usage}. If stop_reason is max_tokens, raise max_tokens."
        )
    data = extract_json(text)
    data["commentary"] = strip_markup(data["commentary"])

    # Carry the selection forward and add a title for the image attachment.
    data["topic"] = selection["topic"]
    data["subtopic"] = selection["subtopic"]
    data.setdefault("title", f"{selection['topic']}: {selection['subtopic']}")

    length, limit = len(data["commentary"]), max_chars(cfg)
    write_json(d / "post.json", data)
    print(f"Draft written ({length} chars, limit {limit}). Preview:\n")
    if length > limit:
        # Not fatal: the post is still worth reviewing, and a rerun costs another
        # billed call. Surface it so it can be rejected or trimmed on approval.
        print(f"::warning::Post is {length - limit} characters over the {limit} limit.")
    print(data["commentary"][:600])


if __name__ == "__main__":
    main()
