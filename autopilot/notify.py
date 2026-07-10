"""Optional: push the draft + image to Telegram so you can see it on your phone.

No-op if TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set. This is a preview
only; the enforced approval gate lives in GitHub (the 'production' environment).
"""
from __future__ import annotations

import argparse
import os

import requests

from .common import out_dir, read_json


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
    caption = post.get("commentary", "")[:1024]  # Telegram caption limit
    image_path = d / "image.png"

    base = f"https://api.telegram.org/bot{token}"
    if image_path.exists():
        with open(image_path, "rb") as img:
            r = requests.post(
                f"{base}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption},
                files={"photo": img},
                timeout=60,
            )
    else:
        r = requests.post(
            f"{base}/sendMessage",
            data={"chat_id": chat_id, "text": caption},
            timeout=60,
        )
    print("Telegram preview status:", r.status_code)


if __name__ == "__main__":
    main()
