// Mode 1: fixed grid, prev/next page buttons, URL-backed state.
import { fetchImages } from "./api.js";
import { getQueryParams, setResultCount } from "./filters.js";
import { showDetail } from "./detail.js";

let page = 0;
let pageSize = 50;

function renderControls(total) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return `
    <div class="pagination">
      <button id="prev-page" ${page === 0 ? "disabled" : ""}>← prev</button>
      <span>page <input id="page-input" type="number" min="1" max="${totalPages}"
        value="${page + 1}" /> / ${totalPages}</span>
      <button id="next-page" ${page >= totalPages - 1 ? "disabled" : ""}>next →</button>
      <select id="page-size">
        ${[20, 50, 100].map(n =>
          `<option value="${n}" ${n === pageSize ? "selected" : ""}>${n}/page</option>`
        ).join("")}
      </select>
    </div>
  `;
}

async function render() {
  syncToHash();
  const content = document.getElementById("content");
  content.innerHTML = '<div class="grid">' +
    Array.from({ length: pageSize }, () => '<div class="skeleton card"></div>').join("") +
    '</div>';

  const params = {
    ...getQueryParams(),
    limit: pageSize,
    offset: page * pageSize,
    order: "id",
  };

  let data;
  try {
    data = await fetchImages(params);
  } catch (e) {
    content.innerHTML = `<div style="color:#f88;padding:20px;">error: ${e.message}</div>`;
    return;
  }

  setResultCount(data.images.length, data.total);

  const grid = document.createElement("div");
  grid.className = "grid";
  for (const img of data.images) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<img loading="lazy" src="${img.thumb_url}" alt="${img.path}" />`;
    card.addEventListener("click", () => showDetail(img.id));
    grid.appendChild(card);
  }
  content.innerHTML = "";
  content.appendChild(grid);

  const controls = document.createElement("div");
  controls.innerHTML = renderControls(data.total);
  content.appendChild(controls.firstElementChild);

  document.getElementById("prev-page").addEventListener("click", () => {
    if (page > 0) { page--; render(); }
  });
  document.getElementById("next-page").addEventListener("click", () => {
    page++; render();
  });
  document.getElementById("page-input").addEventListener("change", (e) => {
    const v = parseInt(e.target.value, 10);
    if (!isNaN(v) && v >= 1) { page = v - 1; render(); }
  });
  document.getElementById("page-size").addEventListener("change", (e) => {
    pageSize = parseInt(e.target.value, 10);
    page = 0;
    render();
  });
}

function syncToHash() {
  const params = new URLSearchParams();
  params.set("page", page + 1);
  params.set("size", pageSize);
  location.hash = params.toString();
}

function loadFromHash() {
  const params = new URLSearchParams(location.hash.slice(1));
  page = Math.max(0, (parseInt(params.get("page"), 10) || 1) - 1);
  pageSize = parseInt(params.get("size"), 10) || 50;
}

export function activate() {
  loadFromHash();
  render();
}

export function refresh() {
  page = 0;
  render();
}
