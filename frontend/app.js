// Entry point: wire up filter sidebar + mode toggle, dispatch to paginated/infinite modules.
import { initFilterSidebar } from "./filters.js";
import { initDetailPanel } from "./detail.js";
import * as paginated from "./paginated.js";
import * as infinite from "./infinite.js";

const MODES = { paginated, infinite };
let currentMode = localStorage.getItem("mode") || "paginated";

function setModeButton() {
  document.getElementById("mode-toggle").textContent = `mode: ${currentMode}`;
}

function switchMode(mode) {
  currentMode = mode;
  localStorage.setItem("mode", mode);
  setModeButton();
  MODES[mode].activate();
}

async function main() {
  setModeButton();
  initDetailPanel();
  await initFilterSidebar(() => MODES[currentMode].refresh());

  document.getElementById("mode-toggle").addEventListener("click", () => {
    switchMode(currentMode === "paginated" ? "infinite" : "paginated");
  });

  MODES[currentMode].activate();
}

main();
