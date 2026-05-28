# booru-auto-tagger

CLI tool + REST API for auto-tagging a local directory of anime images using [WD-tagger](https://huggingface.co/SmilingWolf/wd-v1-4-vits-tagger-v2). Tags are stored in SQLite. Flask serves a tag-aware query API and a browser frontend for review/correction.

**Primary purpose:** sprite and scene image backend for the [misato](https://github.com/funlikely/misato) dating sim — the chatbot queries this API to pick an image matching the current mood, clothing, scene, and content rating.

## Status

Initial implementation in place. See [`PLAN.md`](PLAN.md) for the design spec.

## Quick start

```bash
# 1. install
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt

# 2. configure (edit config.json)
#    image_root: base dir for your images
#    db_path:    where to put booru.db
#    threshold:  inference confidence (default 0.35)

# 3. tag a directory (downloads the WD-tagger model on first run)
python tag.py ./images

# 4. run the server
python server.py
# → frontend at http://127.0.0.1:5000/
# → API health at http://127.0.0.1:5000/health
```

## CLI

```
python tag.py <image_dir> [--db ./booru.db] [--threshold 0.35] [--force] [--image-root <root>]
```

- Walks the directory recursively, finds `.jpg/.jpeg/.png/.webp`.
- Skips already-tagged images unless `--force`.
- Stores paths relative to `--image-root` (defaults to `image_dir`).

## API endpoints

| Method | Path | Notes |
|--------|------|-------|
| `GET`  | `/images` | filters: `posture,body_type,clothing,undress,mood,rating,tag` (comma-separated, OR within / AND across), plus `limit,offset,order=random\|id\|path` |
| `GET`  | `/images/<id>` | full record |
| `GET`  | `/images/random` | same filters as `/images`, returns one |
| `GET`  | `/tags/<category>` | `{ tag: count }` for filter UI |
| `PATCH`| `/images/<id>/tags` | body `{ "category": str, "tags": [str,...] }` — marks `manually_reviewed=1` |
| `GET`  | `/files/<path>` | raw image |
| `GET`  | `/thumbs/<path>` | on-demand thumbnail (cached under `~/.cache/booru-auto-tagger/thumbs/`) |
| `GET`  | `/health` | `{status, image_count}` |

Example for the dating sim:

```
GET /images/random?mood=smile,happy&clothing=school_uniform&rating=safe
```

## Frontend

Served at `/`. Toggle between two modes via the header button (persisted in `localStorage`):

- **paginated** — fixed grid, prev/next buttons, page-size selector
- **infinite** — masonry, `IntersectionObserver`-driven scroll

Click any thumbnail to open the detail panel with per-category chip editor (saves via `PATCH /images/<id>/tags`).

## Files

| File | Role |
|------|------|
| `tag.py` | CLI entrypoint |
| `tagger.py` | WD-tagger ONNX inference |
| `categorize.py` | raw tag → category mapping |
| `db.py` | SQLite schema + queries |
| `server.py` | Flask API + static + frontend |
| `config_util.py` | config.json loader |
| `frontend/` | browser UI (HTML + ES modules) |
| `config.json` | runtime config |

## Quick links

- [Build plan](PLAN.md) — schema, endpoints, categorization, perf notes
- [Misato (consumer)](https://github.com/funlikely/misato)
