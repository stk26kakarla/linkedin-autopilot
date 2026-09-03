"""Warn before the LinkedIn access token expires.

Self-serve apps do not get refresh tokens - those need Marketing Developer
Platform partner approval - so the 60-day access token has to be re-minted by
hand with scripts/get_linkedin_token.py. Left alone that fails silently: the
draft generates, you approve it, and only then does publishing 401.

This runs in the generate job, so the warning reaches Telegram next to the
draft while there is still time to act on it. It never fails the run; a token
problem should not stop you seeing the post.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

import requests

from .common import out_dir

INTROSPECT = "https://www.linkedin.com/oauth/v2/introspectToken"
DEFAULT_WARN_DAYS = 14


def introspect(token: str, client_id: str, client_secret: str) -> dict:
    r = requests.post(
        INTROSPECT,
        data={"token": token, "client_id": client_id, "client_secret": client_secret},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    client_id = os.environ.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET")
    if not (token and client_id and client_secret):
        print("LinkedIn credentials not available; skipping token check.")
        return

    warn_days = int(os.environ.get("TOKEN_WARN_DAYS") or DEFAULT_WARN_DAYS)

    try:
        info = introspect(token, client_id, client_secret)
    except Exception as e:  # never block the run over a check
        print(f"::warning::Could not check LinkedIn token expiry: {e}")
        return

    if info.get("status") != "active":
        message = f"LinkedIn token is not active (status: {info.get('status')}). Re-mint it now."
        print(f"::error::{message}")
        (d / "token_warning.txt").write_text(f"⚠️ {message}", encoding="utf-8")
        return

    expires_at = info.get("expires_at")
    if not expires_at:
        print("Token active; no expiry reported.")
        return

    expiry = dt.datetime.fromtimestamp(int(expires_at))
    days = (expiry - dt.datetime.now()).days
    print(f"LinkedIn token active, expires {expiry:%Y-%m-%d} ({days} days left).")

    if days <= warn_days:
        message = (
            f"LinkedIn token expires in {days} day(s), on {expiry:%d %b}. "
            "Run scripts/get_linkedin_token.py and update the "
            "LINKEDIN_ACCESS_TOKEN secret, or publishing will start failing."
        )
        print(f"::warning::{message}")
        (d / "token_warning.txt").write_text(f"⚠️ {message}", encoding="utf-8")


if __name__ == "__main__":
    main()
