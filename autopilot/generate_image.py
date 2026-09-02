"""Generate the post image with the Gemini image API (Nano Banana Pro).

Nano Banana Pro (gemini-3-pro-image) has no free tier: roughly $0.134/image
at 1K/2K resolution, $0.24/image at 4K (per Google's published pricing as of
Nov 2025). At one image/day that's a few dollars a month, on top of the
Claude research/draft call.
"""
from __future__ import annotations

import argparse
import os

from google import genai
from google.genai import types

from .common import out_dir, read_json, require_env

DEFAULT_MODEL = "gemini-3-pro-image"
DEFAULT_ASPECT_RATIO = "1:1"
DEFAULT_IMAGE_SIZE = "2K"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    post = read_json(d / "post.json")
    prompt = post.get("image_prompt") or post.get("title", "professional abstract illustration")
    model = os.environ.get("GEMINI_IMAGE_MODEL") or DEFAULT_MODEL
    aspect_ratio = os.environ.get("GEMINI_IMAGE_ASPECT_RATIO") or DEFAULT_ASPECT_RATIO
    image_size = os.environ.get("GEMINI_IMAGE_SIZE") or DEFAULT_IMAGE_SIZE

    client = genai.Client(api_key=require_env("GEMINI_API_KEY"))
    resp = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
        ),
    )

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
