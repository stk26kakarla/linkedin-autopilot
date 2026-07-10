# LinkedIn Autopilot

Every day at 11:00 (Europe/London), a GitHub Actions workflow:

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
- A Google Gemini API key (free tier is enough for one image/day): https://aistudio.google.com/apikey
- A LinkedIn developer app (steps below).
- Optional: a Telegram bot, if you want the preview on your phone.

Cost at one post/day is a few cents: a single Claude call with a handful of web searches (search is about $10 per 1,000 searches, so roughly 5 cents/day) plus a free-tier Gemini image. This does not touch your Claude Pro allowance; the API bills separately.

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

Approve in the browser. The script prints your token(s). If it prints a `LINKEDIN_REFRESH_TOKEN`, use that (access tokens are auto-minted each run and last ~60 days; refresh tokens last ~365 days). If no refresh token is returned, use the `LINKEDIN_ACCESS_TOKEN` and re-run this script every ~55 days.

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

Actions tab > Daily LinkedIn Post > Run workflow. The `generate` job runs immediately (manual runs skip the 11:00 gate). Review the draft in the run summary (and Telegram, if configured), then approve the pending `production` deployment to publish. Reject simply by not approving, or cancel the run.

---

## Daily operation

- The workflow fires at 11:00 London time year-round (two UTC cron entries plus a timezone gate handle British Summer Time).
- You get a preview, review it, and approve or ignore.
- Approve = it posts. Do nothing = nothing happens.

## Customising

- Edit `topics.yaml` to change topics, subtopics, voice, guidelines, hashtags, and image style. No code changes needed.
- `selection_mode: rotate` walks the list one pair per day; `random` picks at random.

## Gotchas

- LinkedIn versions its API monthly. If posting returns a version error, set the `LINKEDIN_API_VERSION` variable to the current `YYYYMM` value.
- LinkedIn cannot edit a published post via API; a fix means delete and repost. That is why the human approval sits before publishing.
- If posts show stray backslashes, adjust the `RESERVED` set in `autopilot/post_linkedin.py`.
- LinkedIn has no scheduling field of its own; the cron here is the scheduler.
