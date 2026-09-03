"""One-time helper: get your LinkedIn tokens to store as GitHub secrets.

Run locally on your Mac:

    export LINKEDIN_CLIENT_ID=xxxx
    export LINKEDIN_CLIENT_SECRET=xxxx
    python scripts/get_linkedin_token.py

Requirements in your LinkedIn app:
  - Products enabled: "Sign In with LinkedIn using OpenID Connect" and
    "Share on LinkedIn".
  - Authorized redirect URL: http://localhost:8000/callback

It opens a browser, you approve, and it prints your access token (and refresh
token, if your app is granted one). Store them as repo secrets.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT = "http://localhost:8000/callback"
SCOPES = "openid profile email w_member_social"
# Set GITHUB_REPO to target a repo other than the current directory's.
REPO_ENV = os.environ.get("GITHUB_REPO")

_code = {}


def push_secret(token: str) -> bool:
    """Set LINKEDIN_ACCESS_TOKEN via the gh CLI. False if that is not possible."""
    if not token or not shutil.which("gh"):
        return False
    cmd = ["gh", "secret", "set", "LINKEDIN_ACCESS_TOKEN", "--body", token]
    if REPO_ENV:
        cmd += ["--repo", REPO_ENV]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Could not set the secret automatically: {e.stderr.strip()}")
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        q = urllib.parse.urlparse(self.path)
        if q.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(q.query)
        _code["code"] = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h2>Done. You can close this tab and return to the terminal.</h2>")

    def log_message(self, *_):  # silence
        pass


def main() -> None:
    auth = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT,
            "scope": SCOPES,
        }
    )
    print("Opening browser for LinkedIn authorization...")
    webbrowser.open(auth)
    print("If it did not open, visit:\n", auth)

    server = HTTPServer(("localhost", 8000), Handler)
    while "code" not in _code:
        server.handle_request()

    token_resp = requests.post(
        "https://www.linkedin.com/oauth/v2/accessToken",
        data={
            "grant_type": "authorization_code",
            "code": _code["code"],
            "redirect_uri": REDIRECT,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        timeout=30,
    )
    token_resp.raise_for_status()
    data = token_resp.json()

    access_token = data.get("access_token")
    expires = dt.datetime.now() + dt.timedelta(seconds=int(data.get("expires_in", 0)))

    # Push straight to GitHub rather than making you copy a 500-character token
    # by hand. The browser consent above cannot be automated - that is the whole
    # point of the flow - but everything after it can.
    if push_secret(access_token):
        print(f"\nLINKEDIN_ACCESS_TOKEN updated on {REPO_ENV or 'the current repo'}.")
        print(f"Valid until {expires:%d %b %Y}. Re-run this before then.")
    else:
        print("\n=========== STORE THIS AS A GITHUB SECRET ===========")
        print("LINKEDIN_ACCESS_TOKEN =", access_token)
        print(f"(valid until {expires:%d %b %Y})")
        print("=====================================================")

    if data.get("refresh_token"):
        # Would end the 60-day cycle, but needs Marketing Developer Platform
        # partner approval; self-serve apps do not get one.
        print("\nA refresh token was returned - unusual for a self-serve app.")
        print("LINKEDIN_REFRESH_TOKEN =", data["refresh_token"])
        print("Set it as a secret; post_linkedin.py prefers it and mints access")
        print("tokens automatically, which ends the manual re-minting.")


if __name__ == "__main__":
    main()
