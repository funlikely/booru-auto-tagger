// Mode 2: masonry + IntersectionObserver-driven infinite scroll.
import { fetchImages } from "./api.js";
import { getQueryParams, setResultCount } from "./filters.js";
import { showDetail } from "./detail.js";

const PAGE_SIZE = 50;
let offset = 0;
let total = 0;
let loadedIds = new Set();
let loading = false;
let exhausted = false;
let observer = null;
let backToTop = null;

function makeCard(img) {
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `<img loading="lazy" src="${img.thumb_url}" alt="${img.path}" />`;
  card.addEventListener("click", () => showDetail(img.id));
  return card;
}

async function loadMore() {
  if (loading || exhausted) return;
  loading = true;

  const params = { ...getQueryParams(), limit: PAGE_SIZE, offset, order: "id" };
  let data;
  try {
    data = await fetchImages(params);
  } catch (e) {
    console.error(e);
    loading = false;
    return;
  }

  total = data.total;
  const masonry = document.querySelector(".masonry");
  for (const img of data.images) {
    if (loadedIds.has(img.id)) continue;
    loadedIds.add(img.id);
    masonry.appendChild(makeCard(img));
  }
  offset += data.images.length;
  setResultCount(loadedIds.size, total);

  if (data.images.length < PAGE_SIZE || offset >= total) {
    exhausted = true;
    document.getElementById("sentinel")?.remove();
  }
  loading = false;
}

function ensureBackToTop() {
  if (backToTop) return;
  backToTop = document.createElement("button");
  backToTop.className = "back-to-top";
  backToTop.textContent = "↑";
  backToTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  document.body.appendChild(backToTop);
  window.addEventListener("scroll", () => {
    backToTop.classList.toggle("visible", window.scrollY > window.innerHeight * 3);
  });
}

function reset() {
  offset = 0;
  total = 0;
  loadedIds.clear();
  exhausted = false;
  loading = false;
  if (observer) observer.disconnect();

  const content = document.getElementById("content");
  content.innerHTML = '<div class="masonry"></div><div id="sentinel" style="height:1px"></div>';

  observer = new IntersectionObserver((entries) => {
    if (entries.some(e => e.isIntersecting)) loadMore();
  }, { rootMargin: "600px 0px" });
  observer.observe(document.getElementById("sentinel"));
}

export function activate() {
  ensureBackToTop();
  reset();
}

export function refresh() {
  reset();
}
