# CLAUDE.md

Context and runbook for this repo. `README.md` covers first-time setup; this file
covers how it actually behaves, which decisions are settled, and what has already
broken. Read it before changing anything.

**This repo is public. Never commit tokens, API keys, or secret values.**

---

## What it is

A GitHub Actions pipeline that drafts a LinkedIn post, generates an image, previews
both to Telegram, and publishes only after a human approves. Runs Mon/Wed/Fri.

The editorial intent matters as much as the plumbing: the posts exist to cut through
AI/tech hype and teach, for two audiences at once (engineers who want a better way to
work, and decision makers weighing spend). `mission` in `topics.yaml` is the brief and
is injected as its own section of the system prompt. It permits three angles - correct
a myth, report what genuinely changed, or teach a better way - and explicitly forbids
manufacturing a contrarian take when the hyped thing turns out to be real. That guard
is deliberate: told only to bust myths, the model invents myths to bust.

## Pipeline

`generate` job, all in `autopilot/`:

1. `select_topic` - picks a (topic, subtopic) pair from `topics.yaml` by date
2. `research_and_draft` - one Claude call with server-side web search, returns JSON
3. `generate_image` - one Gemini call using the image prompt Claude wrote
4. `summary` - writes the draft into the Actions run summary
5. `check_token` - warns if the LinkedIn token is near expiry
6. `notify` - sends image + full text + approval link to Telegram
7. uploads everything as the `post-bundle` artifact

`publish` job - gated by the `production` environment (required reviewer). Uploads the
image to LinkedIn and posts. Nothing publishes without approval; ignoring the run is a
valid reject.

## Settled decisions - do not undo these without asking

| Decision | Why |
| --- | --- |
| `claude-sonnet-5` for drafting | User's explicit cost call over Opus. ~£0.51/post → ~£0.15. |
| `web_search` `max_uses: 3` | Results are re-sent every turn of the tool loop, so each extra search compounds well past its $0.01 fee. This is the main Claude cost dial. |
| `gemini-2.5-flash-image` @1K | $0.039 vs $0.134 for `gemini-3-pro-image`. Pro's edge is 4K and text rendering; `topics.yaml` forbids text in images, so it bought nothing. |
| Mon/Wed/Fri, not daily | Cost, and daily is a lot for LinkedIn. |
| Repo is public | Free-plan required-reviewer environments only work on public repos. |
| `max_chars: 1500` | Judgement call. LinkedIn caps at 3000; commonly cited engagement ranges start ~1300. Those sources are marketing blogs, not research - the dwell-time reasoning is what justifies it, not the percentages. |
| Higgsfield ruled out | Subscription exists, but its CLI/MCP auth is a 24h OAuth token with no exportable refresh token. Cannot drive headless CI. Do not re-litigate. |

## Output rules enforced in code, not just prompted

Prompt-only instructions have failed here repeatedly (character limit, emojis), so
these are enforced after generation in `research_and_draft.py`:

- **Em dashes are stripped.** The strongest tell of machine-written text, and a bad
  look for a feed about cutting through AI hype. `—`/`―` become ` - `; a spaced en
  dash becomes `-`; an en dash between numbers (`1300–1500`) is correct typography and
  is preserved. Removals are counted and logged as a workflow warning so a
  non-complying model stays visible.
- **`<cite>` tags are stripped.** Claude's web search wraps quotes in them and they
  would post literally.
- **Character limit is checked**, and over-length logs a warning rather than failing -
  a rerun costs another billed call and the draft is still worth reviewing.

`use_emojis` is instructive, not permissive. "You may use emojis" produced none, which
made the flag look like a setting while behaving like a suggestion.

## Gotchas that cost real time

- **GitHub starts scheduled runs hours late** (3-6h observed). The original gate
  compared the current London hour to 11 and so skipped *every* scheduled run for 11
  days - all reporting green, because a skipped step is not a failure. The gate now
  reads `github.event.schedule` (which cron fired), which delay cannot affect.
  **If runs look green but produce nothing, check the gate step first.**
- **Gemini "prepayment credits are depleted" was not about credits.** The real blocker
  was unfilled India tax info on the billing page. Adding credit does nothing.
- **No Gemini image model has a free tier** any more, including the flash models.
- **LinkedIn retires API versions after ~12 months** → 426. `post_linkedin.py` probes
  `/rest/me` and walks back month by month; a 403 there means the version is fine, only
  426 means retired.
- **LinkedIn renames fields between versions** - `isReuseDisabledByAuthor` became
  `isReshareDisabledByAuthor`, a 422 until fixed.
- **Sonnet 5 thinks by default**; Opus 4.8 did not. Omitting `thinking` cost ~1300
  tokens and truncated the post under the old `max_tokens`. It is 8000 now.
- **Telegram photo captions cap at 1024 chars**, so image and full text go as two
  messages.

## The LinkedIn token cycle

Refresh tokens require Marketing Developer Platform partner approval, which the
self-serve "Share on LinkedIn" products do not get - confirmed in LinkedIn's docs and
empirically. The browser consent step cannot be automated either; that is the flow
proving a member authorised the app, and a runner has no browser. Client-credentials
flow does not help: `w_member_social` needs a member context.

So: **a manual re-mint roughly every 55 days, permanently.** Both ends are softened -
`check_token.py` warns on Telegram from 14 days out, and the script sets the secret
itself.

```bash
export LINKEDIN_CLIENT_ID=... LINKEDIN_CLIENT_SECRET=...
export GITHUB_REPO=stk26kakarla/linkedin-autopilot
python scripts/get_linkedin_token.py     # opens browser, click Allow, pushes the secret
```

Check remaining life any time by POSTing token + client id + secret to
`https://www.linkedin.com/oauth/v2/introspectToken`.

## Commands

```bash
gh workflow run "LinkedIn Post" --repo stk26kakarla/linkedin-autopilot
gh run list   --repo stk26kakarla/linkedin-autopilot --limit 10
gh run view <id> --repo stk26kakarla/linkedin-autopilot --log-failed
gh run download <id> --repo stk26kakarla/linkedin-autopilot -n post-bundle -D ./tmp
gh secret list --repo stk26kakarla/linkedin-autopilot
```

`workflow_dispatch` bypasses the gate, so it cannot test gate behaviour - only a real
scheduled run does that.

Tuning without touching code: `topics.yaml` for mission, topics, voice, limits;
repo Variables `CLAUDE_MODEL`, `GEMINI_IMAGE_MODEL`, `LINKEDIN_API_VERSION` to
override model defaults.

## Working agreements

- Cost matters to the user. Do not silently upgrade models or raise search counts.
- Publishing is public and LinkedIn cannot edit via API - deletion and repost is the
  only fix. Never publish without explicit approval for that specific post.
- Every run that exercises the model costs real money. Diagnose from logs and local
  reproduction before rerunning the pipeline.
- Subtopics must be **subjects with recent coverage to find**, not conclusions to
  defend or evergreen how-tos. They are injected raw as search seeds.

## Open items

- **Source quality.** Posts have cited statistics that appear only on SEO aggregator
  sites (`sqmagazine.co.uk`, `agentmarketcap.ai`) rather than the primary research they
  claim to summarise. For a feed about cutting through hype this is the sharpest
  remaining weakness. Tightening the prompt to refuse figures not traceable to a
  primary source has been proposed and not yet done.
- Posts sometimes lean on figures worth verifying before approval. The human review is
  the control, and the README says so.
