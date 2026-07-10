"""Generate the post image with the Gemini image API (Nano Banana).

At one image per day this sits comfortably inside Google's free tier.
"""
from __future__ import annotations

import argparse
import os

from google import genai

from .common import out_dir, read_json, require_env

DEFAULT_MODEL = "gemini-2.5-flash-image"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    post = read_json(d / "post.json")
    prompt = post.get("image_prompt") or post.get("title", "professional abstract illustration")
    model = os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_MODEL

    client = genai.Client(api_key=require_env("GEMINI_API_KEY"))
    resp = client.models.generate_content(model=model, contents=[prompt])

    image_bytes = None
    for part in resp.candidates[0].content.parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            image_bytes = inline.data
            break

    if not image_bytes:
        raise SystemExit("No image returned by the model. Check the prompt/model/quota.")

    out_path = d / "image.png"
    with open(out_path, "wb") as f:
        f.write(image_bytes)
    print(f"Image saved to {out_path} ({len(image_bytes)} bytes)")


if __name__ == "__main__":
    main()
