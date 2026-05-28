// Shared filter sidebar state and DOM management.
import { fetchTagCounts } from "./api.js";

const CATEGORIES = ["posture", "body_type", "clothing", "undress", "mood"];

export const state = {
  filters: {},   // { posture: ["standing"], ... }
  rating: [],
  rawTag: "",
};

export function getQueryParams() {
  const params = { ...state.filters };
  if (state.rating.length) params.rating = state.rating;
  if (state.rawTag.trim()) params.tag = state.rawTag.trim();
  return params;
}

export async function initFilterSidebar(onChange) {
  for (const cat of CATEGORIES) {
    const container = document.getElementById(`filter-${cat}`);
    const counts = await fetchTagCounts(cat);
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    container.innerHTML = "";
    for (const [tag, count] of entries) {
      const label = document.createElement("label");
      label.innerHTML = `<input type="checkbox" value="${tag}" data-category="${cat}" />
        <span>${tag}</span><span class="count">${count}</span>`;
      container.appendChild(label);
    }
  }

  document.getElementById("apply-filters").addEventListener("click", () => {
    state.filters = {};
    for (const cat of CATEGORIES) {
      const checked = [...document.querySelectorAll(`#filter-${cat} input:checked`)]
        .map(i => i.value);
      if (checked.length) state.filters[cat] = checked;
    }
    state.rating = [...document.querySelectorAll("#filter-rating input:checked")]
      .map(i => i.value);
    state.rawTag = document.getElementById("raw-tag-search").value;
    onChange();
  });

  document.getElementById("clear-filters").addEventListener("click", () => {
    document.querySelectorAll("#sidebar input[type=checkbox]").forEach(i => i.checked = false);
    document.getElementById("raw-tag-search").value = "";
    state.filters = {};
    state.rating = [];
    state.rawTag = "";
    onChange();
  });

  document.getElementById("raw-tag-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("apply-filters").click();
  });
}

export function setResultCount(showing, total) {
  const el = document.getElementById("result-count");
  el.textContent = `${showing.toLocaleString()} of ${total.toLocaleString()} matching`;
}
