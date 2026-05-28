"""CLI: scan a directory of images, tag them with WD-tagger, write to SQLite.

Usage:
    python tag.py <image_dir> [--db ./booru.db] [--threshold 0.35] [--force]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tqdm import tqdm

import db
from categorize import categorize
from config_util import load_config
from tagger import Tagger


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

log = logging.getLogger("tag")


def iter_images(root: Path):
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Auto-tag a directory of anime images.")
    parser.add_argument("image_dir", type=Path, help="Directory to scan recursively.")
    parser.add_argument("--db", default=cfg["db_path"], help="SQLite database path.")
    parser.add_argument(
        "--threshold", type=float, default=cfg["threshold"],
        help="Confidence threshold for WD-tagger (default 0.35).",
    )
    parser.add_argument("--force", action="store_true", help="Re-tag already-tagged images.")
    parser.add_argument(
        "--image-root", type=Path, default=Path(cfg["image_root"]).resolve(),
        help="Base directory used to compute relative paths. Defaults to image_dir.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    image_dir: Path = args.image_dir.resolve()
    image_root: Path = args.image_root.resolve() if args.image_root else image_dir
    if not image_dir.exists():
        log.error("image_dir does not exist: %s", image_dir)
        return 2

    try:
        image_dir.relative_to(image_root)
    except ValueError:
        log.error(
            "image_dir (%s) must be inside image_root (%s)", image_dir, image_root
        )
        return 2

    log.info("DB: %s | image_root: %s | scanning: %s", args.db, image_root, image_dir)
    db.init_db(args.db)
    conn = db.connect(args.db)
    tagger = Tagger(threshold=args.threshold)

    images = list(iter_images(image_dir))
    log.info("Found %d image files", len(images))

    n_tagged = n_skipped = n_failed = 0
    batch_size = 100
    in_tx = False

    try:
        for i, path in enumerate(tqdm(images, unit="img")):
            rel = path.relative_to(image_root).as_posix()
            if not args.force and db.is_tagged(conn, rel):
                n_skipped += 1
                continue
            try:
                result = tagger.tag_image(path)
            except Exception as e:
                log.warning("failed: %s (%s)", rel, e)
                n_failed += 1
                continue
            cat_map, leftover = categorize(result["tags"])
            if not in_tx:
                conn.execute("BEGIN")
                in_tx = True
            db.upsert_image(conn, rel, result["rating"], cat_map, leftover)
            n_tagged += 1

            if n_tagged % batch_size == 0 and in_tx:
                conn.execute("COMMIT")
                in_tx = False
        if in_tx:
            conn.execute("COMMIT")
            in_tx = False
    except BaseException:
        if in_tx:
            conn.execute("ROLLBACK")
        raise

    log.info("done. tagged=%d skipped=%d failed=%d", n_tagged, n_skipped, n_failed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
