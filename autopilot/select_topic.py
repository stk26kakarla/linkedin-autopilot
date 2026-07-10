"""Pick the day's (topic, subtopic) pair and write out/selection.json."""
from __future__ import annotations

import argparse
import datetime as dt
import os
import random

from .common import load_config, out_dir, write_json


def flatten_pairs(cfg: dict) -> list[dict]:
    pairs = []
    for topic in cfg.get("topics", []):
        name = topic["name"]
        for sub in topic.get("subtopics", []):
            pairs.append({"topic": name, "subtopic": sub})
    if not pairs:
        raise SystemExit("No topics/subtopics found in topics.yaml")
    return pairs


def choose(cfg: dict, pairs: list[dict]) -> dict:
    # Manual override (used by workflow_dispatch inputs).
    t_over = os.environ.get("TOPIC_OVERRIDE", "").strip()
    s_over = os.environ.get("SUBTOPIC_OVERRIDE", "").strip()
    if t_over and s_over:
        return {"topic": t_over, "subtopic": s_over}

    mode = cfg.get("selection_mode", "rotate")
    if mode == "random":
        return random.choice(pairs)
    # rotate: advance by one pair each calendar day, cycling through the list.
    idx = dt.date.today().toordinal() % len(pairs)
    return pairs[idx]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out")
    args = ap.parse_args()

    cfg = load_config()
    pairs = flatten_pairs(cfg)
    selection = choose(cfg, pairs)

    d = out_dir(args.out)
    write_json(d / "selection.json", selection)
    print(f"Selected topic: {selection['topic']} / {selection['subtopic']}")


if __name__ == "__main__":
    main()
