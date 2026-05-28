# booru-auto-tagger: build plan

A CLI tool that auto-tags a local directory of anime images using WD-tagger, stores results in SQLite, and serves them via a REST API + optional browser frontend.

**Primary use case:** the database is queried by an external app (a dating sim) to select images based on game state and events.  
**Secondary use case:** a local browser UI for browsing, reviewing, and correcting tags.

---

## Overview

1. Python CLI scans an image directory, runs WD-tagger inference, writes to SQLite
2. Flask server exposes a REST API over the database
3. The dating sim queries the API directly (`GET /images/random?posture=standing&mood=smile`)
4. Browser frontend (two modes, same backend) for manual browsing and tag correction

---

## Repo structure

```
booru-auto-tagger/
├── tag.py              # CLI entrypoint: scan dir, run inference, write DB
├── tagger.py           # WD-tagger ONNX inference wrapper
├── categorize.py       # maps raw Danbooru tags → categories
├── db.py               # SQLite schema, queries, connection management
├── server.py           # Flask app: REST API + serves frontend
├── frontend/
│   ├── index.html      # shell with mode switcher
│   ├── paginated.js    # mode 1: traditional grid + filter sidebar
│   ├── infinite.js     # mode 2: infinite scroll masonry
│   └── style.css
├── requirements.txt
└── README.md
```

---

## Step-by-step tasks

### 1. Project setup
- [ ] Create repo, virtualenv, `requirements.txt`
- [ ] Dependencies: `onnxruntime`, `Pillow`, `numpy`, `huggingface_hub`, `flask`, `flask-cors`
- [ ] No ORM — use `sqlite3` from stdlib directly, keep it simple
- [ ] Pin versions for reproducibility

---

### 2. Database (`db.py`)

Schema:

```sql
CREATE TABLE images (
    id          INTEGER PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,   -- relative to configured image_root
    rating      TEXT,                  -- 'safe' | 'questionable' | 'explicit'
    tagged_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    manually_reviewed INTEGER DEFAULT 0
);

-- One row per tag per image; category is 'posture'/'body_type'/'clothing'/'undress'/'mood'/'raw'
CREATE TABLE tags (
    image_id    INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    tag         TEXT NOT NULL,
    UNIQUE(image_id, category, tag)
);

CREATE INDEX idx_tags_cat_tag  ON tags(category, tag);
CREATE INDEX idx_tags_image_id ON tags(image_id);
CREATE INDEX idx_images_rating ON images(rating);
```

Key functions to implement in `db.py`:
- [ ] `init_db(path)` — create tables if not exist
- [ ] `upsert_image(path, rating, category_tags, raw_tags)` — insert or replace
- [ ] `is_tagged(path)` → bool — for skipping already-processed images
- [ ] `query_images(filters, limit, offset, order)` → list of image rows
  - `filters` is a dict like `{ "posture": ["standing", "sitting"], "mood": ["smile"] }`
  - AND across categories, OR within a category
  - `order`: `"random"` | `"id"` | `"path"`
- [ ] `get_image(id)` → full image record with all tags
- [ ] `update_tags(image_id, category, tags)` — for manual correction UI
- [ ] `get_tag_counts(category)` → `{ tag: count }` — for populating filter UI

---

### 3. Model download (`tagger.py`)
- [ ] On first run, use `huggingface_hub.hf_hub_download` to fetch:
  - Model: `SmilingWolf/wd-v1-4-vits-tagger-v2`
  - Files: `model.onnx`, `selected_tags.csv`
- [ ] Cache to `~/.cache/booru-auto-tagger/`
- [ ] ~30 MB ONNX model, runs on CPU via `onnxruntime` (GPU optional via `onnxruntime-gpu`)

---

### 4. Inference pipeline (`tagger.py`)
- [ ] Load `selected_tags.csv` — maps tag indices to Danbooru tag names + category (0=rating, 4=character, 9=general)
- [ ] Preprocessing: resize image to 448×448, pad to square, normalize to [0,1], BGR channel order
- [ ] Run ONNX session, get sigmoid output vector
- [ ] Apply confidence threshold (default `0.35`, configurable) to select active tags
- [ ] Return: `{ "rating": "safe"|"questionable"|"explicit", "tags": ["tag1", ...] }`
- [ ] Handle corrupt/unreadable images gracefully (log + skip, do not crash run)

---

### 5. Tag categorization (`categorize.py`)

Map raw Danbooru tags to five display categories. Images can match multiple values per category.

**Body posture**
- `standing`, `sitting`, `lying`, `kneeling`, `crouching`, `on_back`, `on_stomach`,
  `leaning_forward`, `arched_back`, `spread_legs`, `crossed_legs`, `arms_up`, `arms_behind_back`

**Body type**
- `loli`, `tall_female`, `muscular`, `curvy`, `large_breasts`, `small_breasts`,
  `medium_breasts`, `wide_hips`, `slim`, `athletic`
- Coverage varies — treat as best-effort

**Clothing type**
- `school_uniform`, `maid`, `swimsuit`, `bikini`, `dress`, `kimono`, `armor`,
  `casual`, `sportswear`, `lingerie`, `naked_apron`, `hoodie`, `military_uniform`
- Group into: uniform / casual / swimwear / formal / fantasy / lingerie

**Degree of undress**
- Primary: WD-tagger `rating` field (`safe` / `questionable` / `explicit`)
- Secondary: `fully_clothed`, `partially_clothed`, `topless`, `bottomless`, `nude`, `underwear_only`
- Combine into a 5-point scale if desired

**Mood / emotional state**
- `smile`, `happy`, `laughing`, `sad`, `crying`, `angry`, `embarrassed`, `blush`,
  `surprised`, `scared`, `serious`, `expressionless`, `sleepy`, `shy`

Implementation:
- [ ] Define mapping as a plain Python dict in `categorize.py`
- [ ] `categorize(raw_tags) → { category: [matched_values] }`
- [ ] Unmatched tags go into `raw` category for future use / search

---

### 6. CLI tagger (`tag.py`)
- [ ] `argparse`: `tag.py <image_dir> [--db ./booru.db] [--threshold 0.35] [--force] [--workers N]`
- [ ] Walk `image_dir` recursively for `.jpg`, `.jpeg`, `.png`, `.webp`
- [ ] Skip already-tagged images (check `db.is_tagged`) unless `--force`
- [ ] Optional: `--workers N` for parallel inference (careful with ONNX session thread safety — use a process pool or serialize)
- [ ] Progress bar via `tqdm`
- [ ] Commits to DB in batches of ~100 for performance
- [ ] Prints summary at end: N tagged, N skipped, N failed

---

### 7. REST API (`server.py`)

This is what the dating sim queries. Keep it simple and stable.

**Endpoints:**

```
GET  /images
     ?posture=standing,sitting   (comma-separated OR within category)
     ?body_type=curvy
     ?clothing=swimsuit
     ?undress=topless
     ?mood=smile,blush
     ?rating=safe                (safe | questionable | explicit)
     ?tag=long_hair              (raw tag search)
     ?order=random|id|path       (default: random)
     ?limit=20                   (default: 20, max: 200)
     ?offset=0
     → { total: N, images: [ { id, path, url, rating, categories, raw_tags } ] }
     (path = relative to image_root; url = ready-to-use /files/<path>)

GET  /images/<id>
     → single image record with full tag data

GET  /images/random              (convenience alias: order=random&limit=1)
     ?<same filters as above>
     → single image object (not wrapped in array)

GET  /tags/<category>
     → { tag: count } for populating filter dropdowns

PATCH /images/<id>/tags          (for manual correction UI)
      body: { "category": "mood", "tags": ["smile", "blush"] }
      → updated image record

GET  /health                     → { status: "ok", image_count: N }
```

Notes:
- [ ] `flask-cors` enabled so the dating sim can query from a different origin/port
- [ ] All image paths returned as relative paths (relative to `image_root` in config)
- [ ] `GET /files/<path:filename>` resolves to `os.path.join(image_root, filename)` — safe against path traversal via `send_from_directory`
- [ ] API responses include both `path` (relative) and a `url` field pre-built as `/files/<path>` so clients don't have to construct it
- [ ] Keep auth out of scope for now — this is a local tool

---

### 8. Frontend (`frontend/`)

Single `index.html` shell that loads one of two JS modules based on a toggle stored in `localStorage`.

#### Shared across both modes
- [ ] Filter sidebar: one collapsible section per category, checkbox list (populated from `GET /tags/<category>`)
- [ ] Rating filter (safe / questionable / explicit checkboxes)
- [ ] Raw tag search box
- [ ] Result count display ("Showing 142 of 3,891 matching images")
- [ ] Mode toggle button (persists in localStorage)
- [ ] Click image → opens detail panel with full tag list + edit controls
- [ ] Tag edit UI: per-category chip editor, saves via `PATCH /images/<id>/tags`

#### Mode 1 — Paginated (`paginated.js`)
- [ ] Fixed grid layout (CSS grid, uniform ~220px cells)
- [ ] Previous / Next page buttons + page number input
- [ ] Page size selector (20 / 50 / 100)
- [ ] URL reflects current filters + page so it's bookmarkable

#### Mode 2 — Infinite scroll (`infinite.js`)
- [ ] Masonry layout (CSS columns or a lightweight lib like `Masonry.js`)
- [ ] `IntersectionObserver` on a sentinel element at the bottom — fires `GET /images?offset=N` when visible
- [ ] Deduplication guard (track loaded IDs to avoid repeats on re-query)
- [ ] "Back to top" button appears after scrolling past ~3 screens
- [ ] Smooth loading skeleton cards while fetching

---

### 9. Image serving
- [ ] `server.py` serves images via `GET /files/<path:filename>` using Flask's `send_from_directory(image_root, filename)` — `image_root` comes from config, never from the request
- [ ] Optional: generate thumbnails on first request, cache to `~/.cache/booru-auto-tagger/thumbs/` mirroring the relative path structure
  - Thumbnails at 400px wide, JPEG quality 80 — big win for frontend performance at 51k images
  - Thumbnail endpoint: `GET /thumbs/<path:filename>` — same relative path, separate endpoint

---

### 10. Configuration
- [ ] Simple `config.json` (or env vars) for:
  - `image_root` — base directory for images
  - `db_path` — path to SQLite file
  - `host` / `port` for the server (default `127.0.0.1:5000`)
  - `threshold` — default inference confidence cutoff
- [ ] Dating sim reads `config.json` too so it knows where the server is

---

## Dating sim integration notes

The dating sim queries `GET /images/random` with filters derived from game state, e.g.:

```
# character is happy, wearing a school uniform, scene is "classroom"
GET /images/random?mood=smile,happy&clothing=school_uniform&rating=safe
```

Recommendations:
- Cache the server URL in the dating sim's config; use the `url` field from responses directly (it's `/files/<relative-path>`) rather than reconstructing paths
- Use `rating` filter aggressively to stay in appropriate content zones per scene
- Consider adding a `character` filter later if your images are organized by character subdirectory — the relative path already encodes this (e.g. `characters/akari/pose001.jpg`), so it's easy to add as a queryable prefix filter
- If the dating sim needs deterministic selection (same image for same game state), pass `?order=id&offset=<deterministic_offset>` — or add a `seed` param to the random query later

---

## Performance notes for 51k images

- Inference: ~1–5s/image on CPU → budget 15–70 hours for a full run. Use `--workers` and/or a GPU via `onnxruntime-gpu` to speed up.
- DB: SQLite handles 51k rows trivially. Filtered queries with indexes should return in <10ms.
- Frontend: with thumbnails, page/scroll loads should feel instant. Without thumbnails, loading 50 full-size images per scroll event will be slow — thumbnails are not optional at this scale.
- Consider running the tagger in batches by subdirectory so you can start using the UI before the full run completes.

---

## Known gotchas

- WD-tagger tag coverage is uneven: clothing and mood are reliable, body type is hit-or-miss
- `rating` from WD-tagger is the most reliable undress signal — weight it heavily
- Images with multiple characters confuse body-type and posture tags
- ONNX session is not thread-safe by default — if parallelizing, use `multiprocessing`, not `threading`
- SQLite has one writer at a time — fine here since only the tagger writes; the server is read-mostly

---

## Possible future extensions

- Character tagging: if subdirectory names = character names, add that as a filter automatically
- Duplicate detection (perceptual hash) before tagging
- Re-tag with a newer model without losing manual corrections (keep `manually_reviewed` flag)
- Export to Hydrus Network
- Auth layer if the server ever leaves localhost
