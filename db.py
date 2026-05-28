"""SQLite layer for the booru auto-tagger.

One row per image; one row per (image, category, tag) in `tags`.
All paths stored relative to the configured `image_root`.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS images (
    id                INTEGER PRIMARY KEY,
    path              TEXT UNIQUE NOT NULL,
    rating            TEXT,
    tagged_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manually_reviewed INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tags (
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    tag      TEXT NOT NULL,
    UNIQUE(image_id, category, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_cat_tag  ON tags(category, tag);
CREATE INDEX IF NOT EXISTS idx_tags_image_id ON tags(image_id);
CREATE INDEX IF NOT EXISTS idx_images_rating ON images(rating);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None)  # autocommit; we use explicit transactions
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def is_tagged(conn: sqlite3.Connection, path: str) -> bool:
    row = conn.execute("SELECT 1 FROM images WHERE path = ?", (path,)).fetchone()
    return row is not None


def upsert_image(
    conn: sqlite3.Connection,
    path: str,
    rating: str | None,
    category_tags: dict[str, list[str]],
    raw_tags: Iterable[str],
) -> int:
    """Insert or replace an image and its tags. Preserves manually_reviewed flag if present.

    Returns the image id.
    """
    existing = conn.execute(
        "SELECT id, manually_reviewed FROM images WHERE path = ?", (path,)
    ).fetchone()

    if existing is None:
        cur = conn.execute(
            "INSERT INTO images (path, rating) VALUES (?, ?)",
            (path, rating),
        )
        image_id = cur.lastrowid
    else:
        image_id = existing["id"]
        conn.execute(
            "UPDATE images SET rating = ?, tagged_at = CURRENT_TIMESTAMP WHERE id = ?",
            (rating, image_id),
        )
        conn.execute("DELETE FROM tags WHERE image_id = ?", (image_id,))

    rows: list[tuple[int, str, str]] = []
    for category, tags in category_tags.items():
        for t in tags:
            rows.append((image_id, category, t))
    for t in raw_tags:
        rows.append((image_id, "raw", t))

    if rows:
        conn.executemany(
            "INSERT OR IGNORE INTO tags (image_id, category, tag) VALUES (?, ?, ?)",
            rows,
        )
    return image_id


def _row_to_image_dict(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    tag_rows = conn.execute(
        "SELECT category, tag FROM tags WHERE image_id = ?", (row["id"],)
    ).fetchall()
    categories: dict[str, list[str]] = {}
    raw_tags: list[str] = []
    for t in tag_rows:
        if t["category"] == "raw":
            raw_tags.append(t["tag"])
        else:
            categories.setdefault(t["category"], []).append(t["tag"])
    return {
        "id": row["id"],
        "path": row["path"],
        "url": f"/files/{row['path']}",
        "thumb_url": f"/thumbs/{row['path']}",
        "rating": row["rating"],
        "tagged_at": row["tagged_at"],
        "manually_reviewed": bool(row["manually_reviewed"]),
        "categories": categories,
        "raw_tags": raw_tags,
    }


def get_image(conn: sqlite3.Connection, image_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        return None
    return _row_to_image_dict(conn, row)


# All non-`raw` categories that have dedicated filter params.
CATEGORY_FILTERS = ("posture", "body_type", "clothing", "undress", "mood")


def query_images(
    conn: sqlite3.Connection,
    filters: dict[str, list[str]] | None = None,
    rating: list[str] | None = None,
    raw_tag: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order: str = "random",
) -> tuple[int, list[dict]]:
    """AND across categories, OR within a category. `raw_tag` is matched against the `raw` category.

    Returns (total_match_count, page_rows).
    """
    filters = filters or {}
    where: list[str] = []
    params: list = []

    for category, values in filters.items():
        if not values:
            continue
        placeholders = ",".join("?" * len(values))
        where.append(
            f"i.id IN (SELECT image_id FROM tags WHERE category = ? AND tag IN ({placeholders}))"
        )
        params.append(category)
        params.extend(values)

    if raw_tag:
        for t in raw_tag:
            where.append(
                "i.id IN (SELECT image_id FROM tags WHERE category = 'raw' AND tag = ?)"
            )
            params.append(t)

    if rating:
        placeholders = ",".join("?" * len(rating))
        where.append(f"i.rating IN ({placeholders})")
        params.extend(rating)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM images i {where_sql}", params
    ).fetchone()["c"]

    if order == "random":
        order_sql = "ORDER BY RANDOM()"
    elif order == "path":
        order_sql = "ORDER BY i.path"
    else:
        order_sql = "ORDER BY i.id"

    rows = conn.execute(
        f"SELECT i.* FROM images i {where_sql} {order_sql} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()

    return total, [_row_to_image_dict(conn, r) for r in rows]


def update_tags(
    conn: sqlite3.Connection, image_id: int, category: str, tags: list[str]
) -> dict | None:
    """Replace all tags in `category` for `image_id`. Marks image as manually_reviewed."""
    if conn.execute("SELECT 1 FROM images WHERE id = ?", (image_id,)).fetchone() is None:
        return None
    conn.execute(
        "DELETE FROM tags WHERE image_id = ? AND category = ?", (image_id, category)
    )
    if tags:
        conn.executemany(
            "INSERT OR IGNORE INTO tags (image_id, category, tag) VALUES (?, ?, ?)",
            [(image_id, category, t) for t in tags],
        )
    conn.execute(
        "UPDATE images SET manually_reviewed = 1 WHERE id = ?", (image_id,)
    )
    return get_image(conn, image_id)


def get_tag_counts(conn: sqlite3.Connection, category: str) -> dict[str, int]:
    rows = conn.execute(
        "SELECT tag, COUNT(*) AS c FROM tags WHERE category = ? GROUP BY tag ORDER BY c DESC",
        (category,),
    ).fetchall()
    return {r["tag"]: r["c"] for r in rows}


def image_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM images").fetchone()["c"]
