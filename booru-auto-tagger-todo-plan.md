# booru-auto-tagger: build plan

A CLI tool that auto-tags a local directory of anime images using WD-tagger and exports a searchable static HTML gallery.

---

## Overview

1. Python CLI scans an image directory
2. WD-1.4-VITS-tagger (ONNX) runs inference on each image
3. Raw Danbooru tags are mapped into five user-facing categories
4. Results saved to `tags.json`
5. A self-contained `index.html` is generated with a filterable grid

---

## Repo structure

```
booru-auto-tagger/
├── tag.py              # main CLI entrypoint
├── tagger.py           # WD-tagger inference wrapper
├── categorize.py       # maps raw Danbooru tags → categories
├── export.py           # renders index.html from tags.json
├── template.html       # HTML/JS template for the gallery
├── requirements.txt
└── README.md
```

---

## Step-by-step tasks

### 1. Project setup
- [ ] Create repo, virtualenv, `requirements.txt`
- [ ] Dependencies: `onnxruntime`, `Pillow`, `numpy`, `huggingface_hub`, `jinja2`
- [ ] Pin versions for reproducibility

### 2. Model download (`tagger.py`)
- [ ] On first run, use `huggingface_hub.hf_hub_download` to fetch:
  - Model: `SmilingWolf/wd-v1-4-vits-tagger-v2`
  - Files: `model.onnx`, `selected_tags.csv`
- [ ] Cache to `~/.cache/booru-auto-tagger/` so it only downloads once
- [ ] Confirm model is ~30 MB ONNX, runs on CPU via `onnxruntime`

### 3. Inference pipeline (`tagger.py`)
- [ ] Load `selected_tags.csv` — this maps tag indices to Danbooru tag names + category (0=rating, 4=character, 9=general)
- [ ] Preprocessing: resize image to 448×448, pad to square, normalize to [0,1], BGR channel order
- [ ] Run ONNX session, get sigmoid output vector
- [ ] Apply confidence threshold (default 0.35) to select active tags
- [ ] Return: `{ "rating": "safe"|"questionable"|"explicit", "tags": ["tag1", ...] }`
- [ ] Handle corrupt/unreadable images gracefully (log and skip)

### 4. Tag categorization (`categorize.py`)
Map raw Danbooru tags to your five display categories. Each image gets one or more values per category. Suggested mappings:

**Body posture**
- Danbooru tags to watch: `standing`, `sitting`, `lying`, `kneeling`, `crouching`, `on_back`, `on_stomach`, `leaning_forward`, `arched_back`, `spread_legs`, `crossed_legs`, `arms_up`, `arms_behind_back`

**Body type**
- `loli`, `shota`, `tall_female`, `muscular`, `athletic`, `curvy`, `large_breasts`, `small_breasts`, `medium_breasts`, `wide_hips`, `slim`
- Note: these tags exist in Danbooru vocabulary but coverage varies

**Clothing type**
- `school_uniform`, `maid`, `swimsuit`, `bikini`, `dress`, `kimono`, `armor`, `casual`, `sportswear`, `lingerie`, `naked_apron`, `hoodie`, `military_uniform`
- Consider grouping into: uniform / casual / swimwear / formal / fantasy

**Degree of undress**
- Primary signal: WD-tagger `rating` field (`safe` / `questionable` / `explicit`)
- Secondary tags: `fully_clothed`, `partially_clothed`, `topless`, `bottomless`, `nude`, `naked`, `underwear_only`
- Combine rating + clothing tags for a 5-point scale if desired

**Mood / emotional state**
- `smile`, `happy`, `laughing`, `sad`, `crying`, `angry`, `embarrassed`, `blush`, `surprised`, `scared`, `serious`, `expressionless`, `sleepy`, `shy`

Implementation notes:
- Build a dict of `{ category: { display_value: [danbooru_tag, ...] } }`
- An image can match multiple values in a category (e.g., both `sitting` and `arms_up`)
- Unknown/unmapped tags are stored in a raw `tags` field for future use

### 5. Main CLI (`tag.py`)
- [ ] `argparse` interface: `tag.py <image_dir> [--output ./output] [--threshold 0.35] [--force]`
- [ ] Walk `image_dir` recursively for `.jpg`, `.jpeg`, `.png`, `.webp`
- [ ] Load existing `tags.json` if present; skip already-tagged images unless `--force`
- [ ] Show progress bar (`tqdm`)
- [ ] Write `tags.json` after each image (so partial runs are resumable)
- [ ] Call `export.py` automatically when done

`tags.json` schema:
```json
{
  "images": [
    {
      "path": "relative/path/to/image.jpg",
      "rating": "safe",
      "categories": {
        "posture": ["standing", "arms_up"],
        "body_type": ["large_breasts"],
        "clothing": ["school_uniform"],
        "undress": ["fully_clothed"],
        "mood": ["smile", "blush"]
      },
      "raw_tags": ["1girl", "solo", "long_hair", "..."]
    }
  ]
}
```

### 6. HTML export (`export.py` + `template.html`)
- [ ] Use Jinja2 to render `template.html` with inlined `tags.json`
- [ ] Output: single `index.html` (images load from their original paths, or optionally copy to output dir)
- [ ] Gallery layout: CSS grid, ~200px thumbnails
- [ ] Filter sidebar: one collapsible section per category, checkbox list of values
  - Filtering logic: AND across categories, OR within a category
- [ ] Search box: filters by raw tag name (substring match)
- [ ] Tag chips shown on hover or below each image
- [ ] Result count shown ("142 of 500 images")
- [ ] All filter/search logic in vanilla JS — no frameworks, no server

### 7. Polish
- [ ] `--copy-images` flag: copies images into output dir so `index.html` is fully portable
- [ ] `--open` flag: open browser automatically after export
- [ ] Sort options in the gallery (by filename, by rating, random)
- [ ] "Unknown" fallback shown for images where a category couldn't be determined
- [ ] README with setup instructions and example output screenshot

---

## Known gotchas

- WD-tagger was trained on Danbooru data; tag coverage is uneven for body type compared to clothing/mood
- The `rating` field from WD-tagger is more reliable than trying to infer undress from clothing tags alone — use it as the primary signal
- Images with multiple characters will confuse body-type tags; single-character images work best
- ONNX CPU inference is ~1–5s/image; a 1000-image library takes ~15–30 min first run

---

## Possible future extensions

- Manual tag correction UI (serve `index.html` via Flask, add POST endpoint to edit `tags.json`)
- Batch re-tag with a newer/different model without losing manual corrections
- Export to Hydrus Network or similar local booru software
- Duplicate detection before tagging
