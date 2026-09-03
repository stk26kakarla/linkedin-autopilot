# LinkedIn Autopilot

Every Monday, Wednesday and Friday at 11:00 (Europe/London), a GitHub Actions workflow:

1. picks a topic and subtopic from `topics.yaml`;
2. asks Claude (with live web search) to research the latest news/trends and draft a post in your voice;
3. generates an image with Gemini;
4. pushes a preview to you and waits for your approval;
5. posts to your LinkedIn profile only after you approve.

The "intelligence" (research, drafting, image concept) is one Claude API call plus one Gemini call. The schedule, approval gate, and posting are plumbing. Nothing is posted without your explicit approval.

---

## What you need

- A GitHub account and a new (empty) repository.
- An Anthropic API key: https://console.anthropic.com
- A Google Gemini API key: https://aistudio.google.com/apikey
- A LinkedIn developer app (steps below).
- Optional: a Telegram bot, if you want the preview on your phone.

Both APIs bill separately from any Claude Pro or Gemini subscription, and both need
credit on the account before they will serve a request.

Cost is roughly **£0.15 per post** (about £2/month at three posts a week):

| Item | Cost |
| --- | --- |
| Claude call (`claude-sonnet-5`, 3 web searches) | ~£0.12 |
| Image (`gemini-2.5-flash-image`) | ~£0.03 |

Two things dominate that, and both are tuned down from the obvious defaults.
Web search results are re-sent on every turn of the tool loop, so each extra
search costs more than the $10/1,000 search fee suggests - `max_uses` in
`autopilot/research_and_draft.py` is the dial. And no Gemini image model has a
free tier any more; `gemini-3-pro-image` is 3.5x the price of the flash model
for 4K and text rendering that a LinkedIn illustration does not need.

---

## 1. Create the LinkedIn app

1. Go to https://developer.linkedin.com and create an app. You must link it to a LinkedIn Company Page; if you do not have one, create a placeholder page first.
2. Open the app, go to Settings, and click Verify to confirm control of the page.
3. Under Products, add: "Sign In with LinkedIn using OpenID Connect" and "Share on LinkedIn". These give the `w_member_social` scope for posting to your own profile; they are self-serve and do not need the multi-week Marketing review.
4. Under Auth, add the redirect URL: `http://localhost:8000/callback`. Note your Client ID and Client Secret.

## 2. Mint your LinkedIn token (one time, local)

On your Mac:

```bash
pip install requests
export LINKEDIN_CLIENT_ID=xxxx
export LINKEDIN_CLIENT_SECRET=xxxx
python scripts/get_linkedin_token.py
```

Approve in the browser. If the `gh` CLI is installed and authenticated, the script sets the `LINKEDIN_ACCESS_TOKEN` secret itself and tells you the expiry date; otherwise it prints the token for you to paste in. Use `GITHUB_REPO=owner/name` to target a specific repo.

**This has to be repeated every ~55 days.** Refresh tokens, which would end that, are only issued to approved Marketing Developer Platform partners, and the self-serve products this uses do not qualify. The browser consent cannot be automated either - that step is LinkedIn confirming a member authorised the app - so the workflow warns you instead: within 14 days of expiry, every run appends a notice to the Telegram preview.

## 3. Push the repo

```bash
cd linkedin-autopilot
git init && git add . && git commit -m "LinkedIn autopilot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## 4. Add secrets

Using the GitHub CLI (`gh`) from the repo folder:

```bash
gh secret set ANTHROPIC_API_KEY
gh secret set GEMINI_API_KEY
gh secret set LINKEDIN_CLIENT_ID
gh secret set LINKEDIN_CLIENT_SECRET
gh secret set LINKEDIN_REFRESH_TOKEN     # or: gh secret set LINKEDIN_ACCESS_TOKEN
# optional preview:
gh secret set TELEGRAM_BOT_TOKEN
gh secret set TELEGRAM_CHAT_ID
```

Or add them in the UI: Settings > Secrets and variables > Actions > New repository secret.

Optional non-secret overrides go under the Variables tab (not Secrets): `CLAUDE_MODEL`, `GEMINI_IMAGE_MODEL`, `LINKEDIN_API_VERSION`.

## 5. Create the approval gate (this is what makes approval mandatory)

1. Settings > Environments > New environment > name it exactly `production`.
2. Enable "Required reviewers" and add yourself.
3. Save.

Now the `publish` job cannot run until you approve. Install the GitHub mobile app to get a push notification and approve from your phone.

## 6. Test it

Actions tab > LinkedIn Post > Run workflow. The `generate` job runs immediately (manual runs skip the 11:00 and day-of-week gate). Review the draft in the run summary (and Telegram, if configured), then approve the pending `production` deployment to publish. Reject simply by not approving, or cancel the run.

---

## Running it

- The workflow fires Monday, Wednesday and Friday at 11:00 London time year-round (two UTC cron entries plus a timezone gate handle British Summer Time).
- You get a preview, review it, and approve or ignore.
- Approve = it posts. Do nothing = nothing happens.

The review matters: the post states figures the model found while researching,
and your name is on it. Check that you stand behind the claims, not just that
it reads well.

## Customising

- Edit `topics.yaml` to change the mission, topics, subtopics, voice, guidelines, hashtags, and image style. No code changes needed.
- `mission` is the editorial brief. It allows three kinds of post - correcting a myth, reporting something genuinely new, or teaching a better way to do a familiar job - and tells the model to pick whichever the evidence supports rather than forcing a contrarian angle. Change this first if the posts feel like the wrong sort of thing.
- `voice.max_chars` (default 1200) is a hard ceiling, enforced in the prompt and checked after generation; going over logs a workflow warning rather than failing the run, since a rerun costs another billed call.
- Subtopics work best as **subjects with something recent to find** ("Cost control on AWS"), not conclusions to defend ("AI doesn't save money") or evergreen how-tos. The model is told to research the last 30 days, so a subtopic with no recent coverage produces a vague post.
- `selection_mode: rotate` steps through the list by date; `random` picks at random.
- To change how often it posts, edit the two `cron` entries in `.github/workflows/linkedin-post.yml` (currently `1,3,5` = Mon/Wed/Fri).
- `CLAUDE_MODEL` and `GEMINI_IMAGE_MODEL` repo Variables override the model defaults without touching code.

## Gotchas

- LinkedIn versions its API monthly and retires versions after about 12 months. `post_linkedin.py` probes for a supported version and walks back automatically, so this should not break unattended; set the `LINKEDIN_API_VERSION` variable to pin a specific `YYYYMM` if you need to.
- The LinkedIn access token lasts ~60 days and this app was not granted a refresh token, so re-run `scripts/get_linkedin_token.py` every ~55 days and update the `LINKEDIN_ACCESS_TOKEN` secret.
- LinkedIn cannot edit a published post via API; a fix means delete and repost. That is why the human approval sits before publishing.
- If posts show stray backslashes, adjust the `RESERVED` set in `autopilot/post_linkedin.py`.
- LinkedIn has no scheduling field of its own; the cron here is the scheduler.
