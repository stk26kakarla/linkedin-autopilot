"""Print a markdown summary of the draft for the GitHub Actions run summary."""
from __future__ import annotations

import argparse

from .common import out_dir, read_json


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()
    d = out_dir(args.out)

    post = read_json(d / "post.json")
    print(f"## Draft for approval: {post.get('title', '')}\n")
    print("### Post text\n")
    print("> " + post.get("commentary", "").replace("\n", "\n> ") + "\n")

    sources = post.get("sources", [])
    if sources:
        print("### Sources\n")
        for s in sources:
            print(f"- [{s.get('title', s.get('url', 'source'))}]({s.get('url', '')})")
        print()

    print("### Image prompt\n")
    print("`" + post.get("image_prompt", "") + "`\n")
    print("_The generated image is attached to this run as the `post-bundle` artifact._\n")
    print("---")
    print("**To publish:** approve the pending `production` deployment below. ")
    print("**To reject:** do nothing (or cancel the run); nothing is posted without approval.")


if __name__ == "__main__":
    main()
