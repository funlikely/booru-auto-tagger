// Per-image detail panel with per-category chip editor.
import { fetchImage, patchTags } from "./api.js";

const CATEGORIES = ["posture", "body_type", "clothing", "undress", "mood"];

let currentImage = null;

export async function showDetail(imageId) {
  const panel = document.getElementById("detail-panel");
  panel.hidden = false;
  document.getElementById("detail-image").src = "";
  document.getElementById("detail-meta").textContent = "loading…";
  document.getElementById("detail-editor").innerHTML = "";

  try {
    currentImage = await fetchImage(imageId);
  } catch (e) {
    document.getElementById("detail-meta").textContent = `error: ${e.message}`;
    return;
  }
  render(currentImage);
}

function render(img) {
  document.getElementById("detail-image").src = img.url;
  document.getElementById("detail-image").alt = img.path;

  const reviewed = img.manually_reviewed
    ? '<span class="reviewed-badge">reviewed</span>' : "";
  document.getElementById("detail-meta").innerHTML = `
    <div><strong>${img.path}</strong>${reviewed}</div>
    <div style="color:#888;font-size:0.85rem;margin-top:4px;">
      rating: ${img.rating ?? "?"} · id: ${img.id}
    </div>
  `;

  const editor = document.getElementById("detail-editor");
  editor.innerHTML = "";
  for (const cat of CATEGORIES) {
    editor.appendChild(buildCategoryEditor(img, cat));
  }
  editor.appendChild(buildRawList(img));
}

function buildCategoryEditor(img, category) {
  const wrap = document.createElement("div");
  wrap.className = "category-editor";

  const tags = [...(img.categories[category] || [])];

  function rerender() {
    wrap.innerHTML = "";
    const h = document.createElement("h4");
    h.textContent = category;
    wrap.appendChild(h);

    for (const tag of tags) {
      const chip = document.createElement("span");
      chip.className = "tag-chip";
      chip.innerHTML = `${tag}<span class="remove">×</span>`;
      chip.querySelector(".remove").addEventListener("click", async () => {
        const next = tags.filter(t => t !== tag);
        await save(img.id, category, next);
      });
      wrap.appendChild(chip);
    }

    const input = document.createElement("input");
    input.placeholder = "add tag, press enter";
    input.addEventListener("keydown", async (e) => {
      if (e.key === "Enter" && input.value.trim()) {
        const next = [...new Set([...tags, input.value.trim()])];
        await save(img.id, category, next);
      }
    });
    wrap.appendChild(input);
  }

  rerender();
  return wrap;
}

function buildRawList(img) {
  const wrap = document.createElement("div");
  wrap.className = "category-editor";
  wrap.innerHTML = `<h4>raw tags (${img.raw_tags.length})</h4>`;
  const tagBox = document.createElement("div");
  tagBox.style.maxHeight = "120px";
  tagBox.style.overflowY = "auto";
  tagBox.style.fontSize = "0.8rem";
  tagBox.style.color = "#aaa";
  tagBox.textContent = img.raw_tags.join(", ");
  wrap.appendChild(tagBox);
  return wrap;
}

async function save(id, category, tags) {
  currentImage = await patchTags(id, category, tags);
  render(currentImage);
}

export function initDetailPanel() {
  document.getElementById("detail-close").addEventListener("click", () => {
    document.getElementById("detail-panel").hidden = true;
    currentImage = null;
  });
}
