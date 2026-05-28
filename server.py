"""Flask REST API + static file/thumbnail/frontend server.

All image paths are relative to the configured image_root. send_from_directory
handles path traversal safety.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
from PIL import Image

import db
from categorize import CATEGORY_TAGS
from config_util import load_config


log = logging.getLogger("server")

CATEGORY_FILTERS = tuple(CATEGORY_TAGS.keys())  # posture, body_type, clothing, undress, mood
VALID_RATINGS = {"safe", "questionable", "explicit"}
MAX_LIMIT = 200
DEFAULT_LIMIT = 20

THUMBS_DIR = Path.home() / ".cache" / "booru-auto-tagger" / "thumbs"


def create_app(config: dict | None = None) -> Flask:
    cfg = config or load_config()
    image_root = Path(cfg["image_root"]).resolve()
    db_path = cfg["db_path"]
    thumb_width = int(cfg.get("thumbnail_width", 400))
    thumb_quality = int(cfg.get("thumbnail_quality", 80))

    db.init_db(db_path)
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=None)
    CORS(app)

    def get_conn():
        # Each request gets a fresh connection — cheap with SQLite, simpler than thread-local pools.
        return db.connect(db_path)

    def parse_csv(name: str) -> list[str]:
        val = request.args.get(name)
        if not val:
            return []
        return [v.strip() for v in val.split(",") if v.strip()]

    def parse_filters() -> dict[str, list[str]]:
        return {cat: parse_csv(cat) for cat in CATEGORY_FILTERS if parse_csv(cat)}

    def parse_paging() -> tuple[int, int, str]:
        try:
            limit = int(request.args.get("limit", DEFAULT_LIMIT))
            offset = int(request.args.get("offset", 0))
        except ValueError:
            abort(400, "limit/offset must be integers")
        limit = max(1, min(limit, MAX_LIMIT))
        offset = max(0, offset)
        order = request.args.get("order", "random")
        if order not in ("random", "id", "path"):
            abort(400, "order must be random|id|path")
        return limit, offset, order

    def parse_ratings() -> list[str]:
        ratings = parse_csv("rating")
        for r in ratings:
            if r not in VALID_RATINGS:
                abort(400, f"invalid rating: {r}")
        return ratings

    # ----- API -----

    @app.get("/health")
    def health():
        conn = get_conn()
        try:
            return jsonify({"status": "ok", "image_count": db.image_count(conn)})
        finally:
            conn.close()

    @app.get("/images")
    def list_images():
        filters = parse_filters()
        ratings = parse_ratings()
        raw_tags = parse_csv("tag")
        limit, offset, order = parse_paging()
        conn = get_conn()
        try:
            total, images = db.query_images(
                conn, filters=filters, rating=ratings, raw_tag=raw_tags,
                limit=limit, offset=offset, order=order,
            )
            return jsonify({"total": total, "limit": limit, "offset": offset, "images": images})
        finally:
            conn.close()

    @app.get("/images/random")
    def random_image():
        filters = parse_filters()
        ratings = parse_ratings()
        raw_tags = parse_csv("tag")
        conn = get_conn()
        try:
            total, images = db.query_images(
                conn, filters=filters, rating=ratings, raw_tag=raw_tags,
                limit=1, offset=0, order="random",
            )
            if not images:
                abort(404, "no images match")
            return jsonify(images[0])
        finally:
            conn.close()

    @app.get("/images/<int:image_id>")
    def get_image(image_id: int):
        conn = get_conn()
        try:
            img = db.get_image(conn, image_id)
            if img is None:
                abort(404)
            return jsonify(img)
        finally:
            conn.close()

    @app.patch("/images/<int:image_id>/tags")
    def patch_tags(image_id: int):
        body = request.get_json(silent=True) or {}
        category = body.get("category")
        tags = body.get("tags")
        if not isinstance(category, str) or not isinstance(tags, list):
            abort(400, "body must be {category: str, tags: [str, ...]}")
        if not all(isinstance(t, str) for t in tags):
            abort(400, "all tags must be strings")
        conn = get_conn()
        try:
            with db.transaction(conn):
                updated = db.update_tags(conn, image_id, category, tags)
            if updated is None:
                abort(404)
            return jsonify(updated)
        finally:
            conn.close()

    @app.get("/tags/<category>")
    def tag_counts(category: str):
        conn = get_conn()
        try:
            return jsonify(db.get_tag_counts(conn, category))
        finally:
            conn.close()

    # ----- Static files -----

    @app.get("/files/<path:filename>")
    def serve_file(filename: str):
        return send_from_directory(image_root, filename)

    @app.get("/thumbs/<path:filename>")
    def serve_thumb(filename: str):
        source = (image_root / filename).resolve()
        # Path-traversal guard: ensure source stays inside image_root.
        try:
            source.relative_to(image_root)
        except ValueError:
            abort(404)
        if not source.exists():
            abort(404)

        thumb_path = (THUMBS_DIR / filename).with_suffix(".jpg")
        if not thumb_path.exists() or thumb_path.stat().st_mtime < source.stat().st_mtime:
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with Image.open(source) as im:
                    im = im.convert("RGB")
                    w, h = im.size
                    if w > thumb_width:
                        im = im.resize(
                            (thumb_width, int(h * thumb_width / w)), Image.LANCZOS
                        )
                    im.save(thumb_path, "JPEG", quality=thumb_quality, optimize=True)
            except Exception as e:
                log.warning("thumbnail failed for %s: %s", filename, e)
                # Fall back to original.
                return send_from_directory(image_root, filename)

        return send_file(thumb_path, mimetype="image/jpeg")

    # ----- Frontend -----

    frontend_dir = Path(__file__).parent / "frontend"

    @app.get("/")
    def index():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/frontend/<path:filename>")
    def serve_frontend(filename: str):
        return send_from_directory(frontend_dir, filename)

    return app


def main():
    import argparse

    cfg = load_config()
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg["host"])
    parser.add_argument("--port", type=int, default=cfg["port"])
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    app = create_app(cfg)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
