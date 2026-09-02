"""Optional: push the draft + image to Telegram so you can see it on your phone.

No-op if TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set. This is a preview
only; the enforced approval gate lives in GitHub (the 'production' environment).
"""
from __future__ import annotations

import argparse
import os

import requests

from .common import out_dir, read_json


def run_url() -> str:
    """Link back to this Actions run, where the approval gate lives."""
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured; skipping preview.")
        return

    post = read_json(d / "post.json")
    commentary = post.get("commentary", "")
    image_path = d / "image.png"
    base = f"https://api.telegram.org/bot{token}"

    # The image goes first with only a short caption: Telegram truncates photo
    # captions at 1024 characters, and these posts routinely run longer.
    if image_path.exists():
        with open(image_path, "rb") as img:
            r = requests.post(
                f"{base}/sendPhoto",
                data={"chat_id": chat_id, "caption": post.get("title", "")[:1024]},
                files={"photo": img},
                timeout=60,
            )
        print("Telegram image status:", r.status_code)

    # The full post follows as a normal message (4096-character limit).
    body = commentary
    run = run_url()
    if run:
        body += f"\n\nApprove or ignore: {run}"
    for chunk in [body[i : i + 4096] for i in range(0, len(body), 4096)] or [""]:
        r = requests.post(
            f"{base}/sendMessage",
            data={"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True},
            timeout=60,
        )
        print("Telegram text status:", r.status_code)


if __name__ == "__main__":
    main()
