"""Publish the approved post (text + image) to your LinkedIn profile.

Runs only after the 'production' environment approval in GitHub Actions.

Auth: prefers a refresh token (LINKEDIN_REFRESH_TOKEN) and mints a fresh access
token each run. If your app was not granted refresh tokens, set a 60-day
LINKEDIN_ACCESS_TOKEN instead and re-mint it periodically with
scripts/get_linkedin_token.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

import requests

from .common import out_dir, read_json

API = "https://api.linkedin.com"
OAUTH = "https://www.linkedin.com/oauth/v2/accessToken"
# LinkedIn versions its API monthly (YYYYMM) and retires versions on a rolling
# ~12-month window. resolve_version() falls back automatically when this ages
# out, so an unattended run does not break the day it expires.
DEFAULT_VERSION = "202608"

# Characters LinkedIn's "commentary" format treats as reserved and that must be
# escaped with a backslash. '#' is intentionally excluded so hashtags render.
RESERVED = set("\\|{}@[]()<>*_~")


def get_access_token() -> str:
    refresh = os.environ.get("LINKEDIN_REFRESH_TOKEN")
    if refresh:
        r = requests.post(
            OAUTH,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh,
                "client_id": os.environ["LINKEDIN_CLIENT_ID"],
                "client_secret": os.environ["LINKEDIN_CLIENT_SECRET"],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["access_token"]
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise SystemExit(
            "Set LINKEDIN_REFRESH_TOKEN (preferred) or LINKEDIN_ACCESS_TOKEN."
        )
    return token


def headers(token: str, version: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": version,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def resolve_version(token: str, preferred: str) -> str:
    """Return a LinkedIn API version the server still accepts.

    A 426 means the version has been retired; any other status means the
    version itself is fine (a 403 here just reflects the scopes this token
    has). Try the preferred version, then walk back month by month.
    """
    candidates, seen = [preferred], set()
    year, month = dt.date.today().year, dt.date.today().month
    for _ in range(15):
        candidates.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12

    for version in candidates:
        if version in seen:
            continue
        seen.add(version)
        r = requests.get(f"{API}/rest/me", headers=headers(token, version), timeout=20)
        if r.status_code != 426:
            if version != preferred:
                print(f"LinkedIn version {preferred} is retired; using {version}.")
            return version
    raise SystemExit(
        f"No supported LinkedIn-Version found (tried {len(seen)}). "
        "Check https://learn.microsoft.com/linkedin/marketing/versioning"
    )


def member_urn(token: str) -> str:
    r = requests.get(
        f"{API}/v2/userinfo",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return f"urn:li:person:{r.json()['sub']}"


def escape_commentary(text: str) -> str:
    return "".join("\\" + c if c in RESERVED else c for c in text)


def upload_image(token: str, version: str, owner: str, image_path) -> str:
    r = requests.post(
        f"{API}/rest/images?action=initializeUpload",
        headers=headers(token, version),
        json={"initializeUploadRequest": {"owner": owner}},
        timeout=30,
    )
    r.raise_for_status()
    value = r.json()["value"]
    upload_url = value["uploadUrl"]
    image_urn = value["image"]

    with open(image_path, "rb") as f:
        put = requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {token}"},
            data=f.read(),
            timeout=120,
        )
    put.raise_for_status()
    return image_urn


def create_post(token: str, version: str, author: str, commentary: str, title: str, image_urn: str) -> str:
    body = {
        "author": author,
        "commentary": escape_commentary(commentary),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "content": {"media": {"title": title[:400], "id": image_urn}},
        "lifecycleState": "PUBLISHED",
        # Renamed from isReuseDisabledByAuthor, which newer versions reject
        # outright (422). False keeps resharing enabled, which is the point of
        # posting; do not drop the field and rely on the API default.
        "isReshareDisabledByAuthor": False,
    }
    r = requests.post(f"{API}/rest/posts", headers=headers(token, version), json=body, timeout=30)
    if r.status_code >= 300:
        raise SystemExit(f"LinkedIn post failed ({r.status_code}): {r.text}")
    return r.headers.get("x-restli-id", r.headers.get("x-linkedin-id", "(unknown urn)"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    post = read_json(d / "post.json")

    token = get_access_token()
    version = resolve_version(token, os.environ.get("LINKEDIN_API_VERSION") or DEFAULT_VERSION)
    author = member_urn(token)
    image_urn = upload_image(token, version, author, d / "image.png")
    urn = create_post(
        token, version, author,
        commentary=post["commentary"],
        title=post.get("title", ""),
        image_urn=image_urn,
    )
    print(f"Published to LinkedIn: {urn}")


if __name__ == "__main__":
    main()
