// Tiny REST helper. The frontend is served from the same origin as the API.

export async function fetchImages(params) {
  const qs = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === null) continue;
    if (Array.isArray(val)) {
      if (val.length) qs.set(key, val.join(","));
    } else {
      qs.set(key, val);
    }
  }
  const res = await fetch(`/images?${qs}`);
  if (!res.ok) throw new Error(`/images failed: ${res.status}`);
  return res.json();
}

export async function fetchTagCounts(category) {
  const res = await fetch(`/tags/${category}`);
  if (!res.ok) return {};
  return res.json();
}

export async function fetchImage(id) {
  const res = await fetch(`/images/${id}`);
  if (!res.ok) throw new Error(`/images/${id} failed: ${res.status}`);
  return res.json();
}

export async function patchTags(id, category, tags) {
  const res = await fetch(`/images/${id}/tags`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, tags }),
  });
  if (!res.ok) throw new Error(`PATCH failed: ${res.status}`);
  return res.json();
}
