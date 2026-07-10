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

import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

CLIENT_ID = os.environ["LINKEDIN_CLIENT_ID"]
CLIENT_SECRET = os.environ["LINKEDIN_CLIENT_SECRET"]
REDIRECT = "http://localhost:8000/callback"
SCOPES = "openid profile email w_member_social"

_code = {}


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

    print("\n=========== STORE THESE AS GITHUB SECRETS ===========")
    print("LINKEDIN_ACCESS_TOKEN =", data.get("access_token"))
    if data.get("refresh_token"):
        print("LINKEDIN_REFRESH_TOKEN =", data["refresh_token"])
        print("(refresh token present: prefer this; access tokens expire in ~60 days)")
    else:
        print("LINKEDIN_REFRESH_TOKEN = (none returned)")
        print("Your app was not granted refresh tokens. Use LINKEDIN_ACCESS_TOKEN and")
        print("re-run this script every ~55 days to mint a new one.")
    print("=====================================================")


if __name__ == "__main__":
    main()
