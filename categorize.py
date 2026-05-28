"""Map raw Danbooru tags to display categories.

Categories: posture, body_type, clothing, undress, mood.
Tags not matched in any category are returned under 'raw'.
"""

from __future__ import annotations


POSTURE = {
    "standing", "sitting", "lying", "kneeling", "crouching", "squatting",
    "on_back", "on_stomach", "leaning_forward", "arched_back", "spread_legs",
    "crossed_legs", "arms_up", "arms_behind_back", "arms_behind_head",
    "bent_over", "all_fours", "fetal_position", "indian_style",
    "walking", "running", "jumping",
}

BODY_TYPE = {
    "loli", "tall_female", "tall", "muscular", "muscular_female", "curvy",
    "large_breasts", "small_breasts", "medium_breasts", "huge_breasts", "flat_chest",
    "wide_hips", "slim", "athletic", "petite", "thick_thighs", "plump",
}

CLOTHING = {
    "school_uniform", "serafuku", "maid", "swimsuit", "bikini", "one-piece_swimsuit",
    "dress", "kimono", "yukata", "armor", "casual", "sportswear", "gym_uniform",
    "lingerie", "naked_apron", "hoodie", "military_uniform", "nurse",
    "cheerleader", "miko", "police_uniform", "business_suit", "cocktail_dress",
    "wedding_dress", "pajamas", "sweater", "t-shirt", "shirt", "skirt", "pants",
    "shorts", "jeans", "jacket", "coat", "bodysuit",
}

# Group clothing into looser scene categories (informational; not exposed yet).
CLOTHING_GROUPS = {
    "uniform": {"school_uniform", "serafuku", "maid", "military_uniform", "nurse",
                "police_uniform", "miko", "cheerleader", "gym_uniform"},
    "casual": {"casual", "hoodie", "t-shirt", "shirt", "skirt", "pants",
               "shorts", "jeans", "jacket", "coat", "sweater", "pajamas"},
    "swimwear": {"swimsuit", "bikini", "one-piece_swimsuit"},
    "formal": {"dress", "kimono", "yukata", "business_suit", "cocktail_dress",
               "wedding_dress"},
    "fantasy": {"armor"},
    "lingerie": {"lingerie", "naked_apron", "bodysuit"},
}

UNDRESS = {
    "fully_clothed", "partially_clothed", "topless", "bottomless", "nude",
    "completely_nude", "underwear_only", "bra", "panties", "shirt_lift",
    "skirt_lift", "clothes_pull", "open_clothes",
}

MOOD = {
    "smile", "happy", "laughing", "sad", "crying", "tears", "angry",
    "embarrassed", "blush", "surprised", "shocked", "scared", "frightened",
    "serious", "expressionless", "sleepy", "shy", "smug", "pout",
    "open_mouth", "grin", "frown",
}

CATEGORY_TAGS = {
    "posture": POSTURE,
    "body_type": BODY_TYPE,
    "clothing": CLOTHING,
    "undress": UNDRESS,
    "mood": MOOD,
}

_TAG_TO_CATEGORY: dict[str, str] = {}
for _cat, _tags in CATEGORY_TAGS.items():
    for _t in _tags:
        _TAG_TO_CATEGORY[_t] = _cat


def categorize(raw_tags: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    """Split tags into (category_map, leftover_raw_tags).

    The category map only contains categories with at least one matched tag.
    Leftover tags are everything not matched by any category.
    """
    category_map: dict[str, list[str]] = {}
    leftover: list[str] = []
    for t in raw_tags:
        cat = _TAG_TO_CATEGORY.get(t)
        if cat is None:
            leftover.append(t)
        else:
            category_map.setdefault(cat, []).append(t)
    return category_map, leftover


def clothing_group(clothing_tags: list[str]) -> list[str]:
    """Map a list of matched clothing tags to scene-level group labels."""
    groups: list[str] = []
    for group, tags in CLOTHING_GROUPS.items():
        if any(t in tags for t in clothing_tags):
            groups.append(group)
    return groups
