# booru-auto-tagger

CLI tool + REST API for auto-tagging a local directory of anime images using [WD-tagger](https://huggingface.co/SmilingWolf/wd-v1-4-vits-tagger-v2). Tags are stored in SQLite. Flask serves a tag-aware query API and a browser frontend for review/correction.

**Primary purpose:** sprite and scene image backend for the [misato](https://github.com/funlikely/misato) dating sim — the chatbot queries this API to pick an image matching the current mood, clothing, scene, and content rating.

## Status

Planning only. No code yet. The full build plan lives in [`PLAN.md`](PLAN.md).

## Quick links

- [Build plan](PLAN.md) — schema, endpoints, categorization, perf notes
- [Misato (consumer)](https://github.com/funlikely/misato)
