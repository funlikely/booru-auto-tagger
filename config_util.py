"""Small helper: load config.json with sensible defaults."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULTS = {
    "image_root": "./images",
    "db_path": "./booru.db",
    "host": "127.0.0.1",
    "port": 5000,
    "threshold": 0.35,
    "thumbnail_width": 400,
    "thumbnail_quality": 80,
}


def load_config(path: str | Path = "config.json") -> dict:
    p = Path(path)
    cfg = dict(DEFAULTS)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            cfg.update(json.load(f))
    local = p.with_name(p.stem + ".local" + p.suffix)
    if local.exists():
        with open(local, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg
