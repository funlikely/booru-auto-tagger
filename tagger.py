"""WD-tagger ONNX inference wrapper.

Downloads SmilingWolf/wd-v1-4-vits-tagger-v2 on first use, caches to
~/.cache/booru-auto-tagger/, and runs sigmoid-thresholded inference.

selected_tags.csv schema (Danbooru categories):
    0 = general/rating tags grouped under category_id 9
    columns: tag_id, name, category, count
    category: 9 = rating, 0 = general, 4 = character
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image


log = logging.getLogger(__name__)

MODEL_REPO = "SmilingWolf/wd-v1-4-vits-tagger-v2"
MODEL_FILE = "model.onnx"
TAGS_FILE = "selected_tags.csv"
CACHE_DIR = Path.home() / ".cache" / "booru-auto-tagger"


@dataclass
class TagEntry:
    name: str
    category: int  # 9=rating, 0=general, 4=character


class Tagger:
    def __init__(self, threshold: float = 0.35, providers: list[str] | None = None):
        self.threshold = threshold
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        model_path = hf_hub_download(MODEL_REPO, MODEL_FILE, cache_dir=str(CACHE_DIR))
        tags_path = hf_hub_download(MODEL_REPO, TAGS_FILE, cache_dir=str(CACHE_DIR))

        self.tags = self._load_tags(tags_path)

        providers = providers or ort.get_available_providers()
        self.session = ort.InferenceSession(model_path, providers=providers)
        self.input_name = self.session.get_inputs()[0].name
        # WD-tagger v2 input is (1, 448, 448, 3)
        self.input_size = self.session.get_inputs()[0].shape[1]

    @staticmethod
    def _load_tags(csv_path: str) -> list[TagEntry]:
        tags: list[TagEntry] = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tags.append(TagEntry(name=row["name"], category=int(row["category"])))
        return tags

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        # WD-tagger expects: square padded to white, resized to input_size, BGR, float32 in [0, 255]
        img = image.convert("RGBA")
        canvas = Image.new("RGBA", img.size, (255, 255, 255))
        canvas.alpha_composite(img)
        img = canvas.convert("RGB")

        w, h = img.size
        side = max(w, h)
        square = Image.new("RGB", (side, side), (255, 255, 255))
        square.paste(img, ((side - w) // 2, (side - h) // 2))

        size = self.input_size
        square = square.resize((size, size), Image.BICUBIC)

        arr = np.asarray(square, dtype=np.float32)
        # RGB -> BGR
        arr = arr[:, :, ::-1]
        return np.expand_dims(arr, 0)

    def tag_image(self, path: str | Path) -> dict:
        """Return {'rating': str|None, 'tags': [str, ...]} for an image file."""
        with Image.open(path) as im:
            im.load()
            batch = self._preprocess(im)

        probs = self.session.run(None, {self.input_name: batch})[0][0]

        rating_scores: dict[str, float] = {}
        active_tags: list[str] = []
        for tag, score in zip(self.tags, probs):
            if tag.category == 9:  # rating
                rating_scores[tag.name] = float(score)
            else:
                if score >= self.threshold:
                    active_tags.append(tag.name)

        rating = _map_rating(rating_scores)
        return {"rating": rating, "tags": active_tags}


def _map_rating(scores: dict[str, float]) -> str | None:
    """WD-tagger emits four rating tags: general, sensitive, questionable, explicit.

    Map to our 3-tier scale.
    """
    if not scores:
        return None
    top = max(scores, key=scores.get)
    if top in ("general", "sensitive"):
        return "safe" if top == "general" else "questionable"
    if top == "questionable":
        return "questionable"
    if top == "explicit":
        return "explicit"
    return None
