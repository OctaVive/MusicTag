const bootState = window.MUSICTAG_BOOT || { locked: true };
let unlocked = !bootState.locked;
let selectedFileNode = null;
let selectedPathValue = "";
let treeData = null;
let treeFilter = "";
const expandedFolders = new Set(["."]);
const selectedFiles = new Set();
const placeholderCover =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(
    "<svg xmlns='http://www.w3.org/2000/svg' width='400' height='400'>" +
      "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>" +
      "<stop offset='0%' stop-color='#1f2a47'/><stop offset='100%' stop-color='#0b1326'/></linearGradient></defs>" +
      "<rect width='100%' height='100%' fill='url(#g)'/>" +
      "<text x='50%' y='52%' dominant-baseline='middle' text-anchor='middle' fill='#9db7ff' font-family='Arial' font-size='26'>No Cover</text>" +
    "</svg>"
  );

const treeRoot = document.getElementById("treeRoot");
const treeFilterInput = document.getElementById("treeFilterInput");
const treeEmptyState = document.getElementById("treeEmptyState");
const treeResizeHandle = document.getElementById("treeResizeHandle");
const lockBtn = document.getElementById("lockBtn");
const saveBtn = document.getElementById("saveBtn");
const themeSelect = document.getElementById("themeSelect");
const toolsCloseBtn = document.getElementById("toolsCloseBtn");
const toolsDrawer = document.getElementById("toolsDrawer");
const toolsBackdrop = document.getElementById("toolsBackdrop");
const statusMessage = document.getElementById("statusMessage");
const saveProgressWrap = document.getElementById("saveProgressWrap");
const saveProgressBar = document.getElementById("saveProgressBar");
const saveProgressLabel = document.getElementById("saveProgressLabel");
const bulkStatus = document.getElementById("bulkStatus");
const bulkApplyHint = document.getElementById("bulkApplyHint");
const bulkModeSwitch = document.getElementById("bulkModeSwitch");
const bulkModeCompilationBtn = document.getElementById("bulkModeCompilationBtn");
const bulkModeTemplateBtn = document.getElementById("bulkModeTemplateBtn");
const bulkModeHint = document.getElementById("bulkModeHint");
const tagForm = document.getElementById("tagForm");
const selectedPath = document.getElementById("selectedPath");
const reloadTreeBtn = document.getElementById("reloadTreeBtn");
const coverInput = document.getElementById("coverInput");
const coverPreview = document.getElementById("coverPreview");
const audioPreview = document.getElementById("audioPreview");
const playerCoverThumb = document.getElementById("playerCoverThumb");
const playerTrackTitle = document.getElementById("playerTrackTitle");
const playerTrackSubtitle = document.getElementById("playerTrackSubtitle");
const playerBackBtn = document.getElementById("playerBackBtn");
const playerPlayPauseBtn = document.getElementById("playerPlayPauseBtn");
const playerPlayPauseIcon = document.getElementById("playerPlayPauseIcon");
const playerForwardBtn = document.getElementById("playerForwardBtn");
const playerSeek = document.getElementById("playerSeek");
const playerCurrentTime = document.getElementById("playerCurrentTime");
const playerDuration = document.getElementById("playerDuration");
const playerVolume = document.getElementById("playerVolume");
const titleInput = document.getElementById("titleInput");
const artistInput = document.getElementById("artistInput");
const parserPattern = document.getElementById("parserPattern");
const previewParserBtn = document.getElementById("previewParserBtn");
const applyParserBtn = document.getElementById("applyParserBtn");
const presetNameInput = document.getElementById("presetNameInput");
const savePresetBtn = document.getElementById("savePresetBtn");
const loadPresetsBtn = document.getElementById("loadPresetsBtn");
const presetSelect = document.getElementById("presetSelect");
const applyPresetBtn = document.getElementById("applyPresetBtn");
const previewNumberBtn = document.getElementById("previewNumberBtn");
const applyNumberBtn = document.getElementById("applyNumberBtn");
const previewBulkBtn = document.getElementById("previewBulkBtn");
const undoLastBtn = document.getElementById("undoLastBtn");
const qualityCheckBtn = document.getElementById("qualityCheckBtn");
const removeCoverBulkBtn = document.getElementById("removeCoverBulkBtn");
const bulkCoverInput = document.getElementById("bulkCoverInput");
const setCoverBulkBtn = document.getElementById("setCoverBulkBtn");
const bulkCoverApplyCheckbox = document.getElementById("bulkCoverApplyCheckbox");
const lookupBtn = document.getElementById("lookupBtn");
const lookupArtistInput = document.getElementById("lookupArtistInput");
const lookupAlbumInput = document.getElementById("lookupAlbumInput");
const lookupResults = document.getElementById("lookupResults");
const bulkOnlyBlocks = Array.from(document.querySelectorAll(".bulk-only"));
const singleOnlyBlocks = Array.from(document.querySelectorAll(".single-only"));
const bulkAdvancedFields = Array.from(document.querySelectorAll(".bulk-advanced-fields"));
const bulkApplyCheckboxes = Array.from(document.querySelectorAll(".bulk-apply-checkbox"));
const tagInputs = [
  titleInput,
  artistInput,
  document.getElementById("albumInput"),
  document.getElementById("albumArtistInput"),
  document.getElementById("trackInput"),
  document.getElementById("genreInput"),
  document.getElementById("yearInput"),
  document.getElementById("discInput"),
];
let isToolsOpen = localStorage.getItem("musictag.toolsOpen") === "1";
let bulkMode = localStorage.getItem("musictag.bulkMode") || "compilation";
let wasBulkModeActive = false;
let saveProgressTimer = null;
let saveProgressValue = 0;
const treeWidthStorageKey = "musictag.treeWidth";
const themeStorageKey = "musictag.theme";
const treeCompactMedia = window.matchMedia("(max-width: 940px)");
let treeResizeSession = null;
const treeCoverCache = new Map();
const treeCoverPending = new Map();
let treeThumbObserver = null;
let playerIsSeeking = false;
isToolsOpen = false;

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(";").shift();
  return "";
}

function getCsrfToken() {
  return getCookie("csrftoken") || document.querySelector("meta[name='csrf-token']")?.getAttribute("content") || "";
}

async function parseJsonSafe(res) {
  const text = await res.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { error: text };
  }
}

function setStatus(text, type = "") {
  statusMessage.textContent = text;
  statusMessage.className = `status-message ${type}`.trim();
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  const mins = Math.floor(whole / 60);
  const secs = whole % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

function syncPlayerButtonLabel() {
  if (!playerPlayPauseBtn) return;
  if (playerPlayPauseIcon) {
    playerPlayPauseIcon.textContent = audioPreview.paused ? "▶" : "⏸";
  }
}

function syncPlayerProgress() {
  if (!playerSeek || !playerCurrentTime || !playerDuration) return;
  const duration = Number.isFinite(audioPreview.duration) ? audioPreview.duration : 0;
  const current = Number.isFinite(audioPreview.currentTime) ? audioPreview.currentTime : 0;
  playerCurrentTime.textContent = formatTime(current);
  playerDuration.textContent = formatTime(duration);
  if (!playerIsSeeking) {
    const ratio = duration > 0 ? current / duration : 0;
    playerSeek.value = String(Math.round(ratio * 1000));
  }
}

function syncPlayerMeta(tags = {}, filePath = "") {
  if (playerCoverThumb) playerCoverThumb.src = tags.cover_data_url || placeholderCover;
  if (playerTrackTitle) playerTrackTitle.textContent = tags.TITLE || filePath.split("/").pop() || "No track selected";
  if (playerTrackSubtitle) {
    const artist = tags.ARTIST || "";
    const album = tags.ALBUM || "";
    playerTrackSubtitle.textContent = [artist, album].filter(Boolean).join(" - ") || "Select a file to preview audio";
  }
}

function isTypingTarget(target) {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

async function navigateTrack(direction) {
  const fileButtons = Array.from(treeRoot.querySelectorAll(".file-node[data-path]"));
  if (!fileButtons.length) return;
  const currentPath = selectedPathValue || selectedPath.value;
  const currentIndex = fileButtons.findIndex((button) => button.dataset.path === currentPath);
  const fallbackIndex = direction > 0 ? 0 : fileButtons.length - 1;
  const baseIndex = currentIndex >= 0 ? currentIndex : fallbackIndex;
  const nextIndex = Math.max(0, Math.min(fileButtons.length - 1, baseIndex + direction));
  if (nextIndex === currentIndex && currentIndex >= 0) return;
  const target = fileButtons[nextIndex];
  if (!target) return;
  await selectFile(target);
}

function startSaveProgress(labelText) {
  if (saveProgressTimer) {
    clearInterval(saveProgressTimer);
  }
  saveProgressValue = 0;
  saveProgressWrap.classList.remove("hidden");
  saveProgressLabel.textContent = labelText || "Saving changes...";
  saveProgressBar.style.width = "0%";
  saveProgressTimer = setInterval(() => {
    saveProgressValue = Math.min(92, saveProgressValue + Math.max(2, (100 - saveProgressValue) * 0.08));
    saveProgressBar.style.width = `${Math.round(saveProgressValue)}%`;
  }, 140);
}

function finishSaveProgress(success, labelText) {
  if (saveProgressTimer) {
    clearInterval(saveProgressTimer);
    saveProgressTimer = null;
  }
  saveProgressBar.style.width = "100%";
  saveProgressLabel.textContent = labelText || (success ? "Save complete." : "Save failed.");
  setTimeout(() => {
    saveProgressWrap.classList.add("hidden");
    saveProgressBar.style.width = "0%";
  }, 500);
}

function getActivePaths() {
  if (selectedFiles.size > 0) return Array.from(selectedFiles);
  if (selectedPath.value) return [selectedPath.value];
  return [];
}

function isBulkMode() {
  return selectedFiles.size > 1;
}

function setToolsOpen(nextOpen) {
  isToolsOpen = Boolean(nextOpen);
  toolsDrawer.classList.toggle("hidden", !isToolsOpen);
  toolsBackdrop.classList.toggle("hidden", !isToolsOpen);
  toolsDrawer.setAttribute("aria-hidden", isToolsOpen ? "false" : "true");
  toolsBackdrop.setAttribute("aria-hidden", isToolsOpen ? "false" : "true");
  localStorage.setItem("musictag.toolsOpen", isToolsOpen ? "1" : "0");
}

function syncLockUi() {
  const bulk = isBulkMode();
  const compilationMode = bulkMode === "compilation";
  tagInputs.forEach((input) => {
    input.readOnly = !unlocked;
  });
  if (bulk) {
    titleInput.readOnly = true;
    artistInput.readOnly = compilationMode || !unlocked;
  }
  bulkAdvancedFields.forEach((el) => el.classList.toggle("hidden", bulk && compilationMode));
  bulkModeSwitch.classList.toggle("hidden", !bulk);
  bulkModeHint.classList.toggle("hidden", !(bulk && bulkMode === "template"));
  bulkModeCompilationBtn.classList.toggle("active", bulkMode === "compilation");
  bulkModeTemplateBtn.classList.toggle("active", bulkMode === "template");
  saveBtn.disabled = !unlocked || (selectedFiles.size === 0 && !selectedPath.value);
  lockBtn.textContent = unlocked ? "Lock" : "Unlock";
  lockBtn.classList.toggle("locked", !unlocked);
  const allowBulkCoverEdit = bulk && bulkCoverApplyCheckbox && bulkCoverApplyCheckbox.checked;
  coverInput.disabled = !unlocked || (bulk && !allowBulkCoverEdit);
  bulkStatus.textContent = bulk ? `Bulk mode: ${selectedFiles.size} files selected` : "Single edit mode";
  bulkOnlyBlocks.forEach((el) => el.classList.toggle("hidden", !bulk));
  singleOnlyBlocks.forEach((el) => el.classList.toggle("hidden", bulk));
  bulkApplyHint.classList.toggle("hidden", !bulk);
  bulkApplyCheckboxes.forEach((checkbox) => {
    const tag = checkbox.dataset.tag;
    const allowedInCompilation = new Set(["ALBUM", "ALBUMARTIST", "YEAR", "GENRE"]);
    const allowed = !bulk
      ? false
      : (compilationMode ? allowedInCompilation.has(tag) : tag !== "TITLE");
    checkbox.classList.toggle("hidden", !allowed);
    checkbox.disabled = !allowed;
    if (!allowed) checkbox.checked = false;
    const row = checkbox.closest(".tag-field");
    if (row) row.classList.toggle("unchecked", bulk && allowed && !checkbox.checked);
  });
  if (bulkCoverApplyCheckbox) {
    bulkCoverApplyCheckbox.disabled = !bulk;
    if (!bulk) bulkCoverApplyCheckbox.checked = false;
  }
  if (bulk && !wasBulkModeActive) {
    resetBulkApplyChecks();
  }
  if (!bulk) {
    resetBulkApplyChecks();
  }
  wasBulkModeActive = bulk;
}

function setBulkMode(mode) {
  if (!["compilation", "template"].includes(mode)) return;
  bulkMode = mode;
  localStorage.setItem("musictag.bulkMode", bulkMode);
  resetBulkApplyChecks();
  syncLockUi();
}

function resetBulkApplyChecks() {
  bulkApplyCheckboxes.forEach((checkbox) => {
    checkbox.checked = false;
    const row = checkbox.closest(".tag-field");
    if (row) row.classList.add("unchecked");
  });
}

function clearSelectedTrackUi() {
  selectedPathValue = "";
  selectedPath.value = "";
  if (selectedFileNode) selectedFileNode.classList.remove("selected");
  selectedFileNode = null;
  titleInput.value = "";
  artistInput.value = "";
  document.getElementById("albumInput").value = "";
  document.getElementById("albumArtistInput").value = "";
  document.getElementById("trackInput").value = "";
  document.getElementById("genreInput").value = "";
  document.getElementById("yearInput").value = "";
  document.getElementById("discInput").value = "";
  coverPreview.src = placeholderCover;
  audioPreview.pause();
  audioPreview.removeAttribute("src");
  syncPlayerMeta();
  syncPlayerProgress();
  syncPlayerButtonLabel();
}

async function fetchTree() {
  const res = await fetch("/api/tree");
  const body = await parseJsonSafe(res);
  if (!res.ok) throw new Error(body.error || "Unable to load directory tree");
  treeData = body.tree;
  renderTree();
}

function renderTree() {
  if (!treeData) {
    treeRoot.innerHTML = "";
    treeEmptyState.hidden = false;
    return;
  }
  treeRoot.innerHTML = "";
  const filtered = filterTree(treeData, treeFilter);
  if (!filtered || !filtered.children?.length) {
    treeEmptyState.hidden = false;
    return;
  }
  treeEmptyState.hidden = true;
  const root = createNode(filtered, 0);
  root.open = true;
  treeRoot.appendChild(root);
  initializeTreeThumbnails();
  rebindSelectedNode();
  refreshFolderCheckStates();
}

function createNode(node, depth) {
  if (node.type === "file") {
    const row = document.createElement("div");
    row.className = "file-row";
    row.dataset.depth = String(depth);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "tree-checkbox";
    checkbox.checked = selectedFiles.has(node.path);
    checkbox.addEventListener("click", (e) => e.stopPropagation());
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedFiles.add(node.path);
      else selectedFiles.delete(node.path);
      syncLockUi();
      refreshFolderCheckStates();
    });

    const button = document.createElement("button");
    button.className = "file-node";
    button.type = "button";
    button.innerHTML = [
      "<span class='tree-thumb' aria-hidden='true'>",
      "  <img class='tree-thumb-img hidden' alt=''>",
      "  <span class='tree-thumb-fallback'>♪</span>",
      "</span>",
      `<span class='tree-file-name'>${escapeHtml(node.name)}</span>`,
    ].join("");
    button.dataset.path = node.path;
    button.dataset.depth = String(depth);
    button.addEventListener("click", () => selectFile(button));
    button.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        selectFile(button);
      }
    });
    row.appendChild(checkbox);
    row.appendChild(button);
    return row;
  }

  const details = document.createElement("details");
  details.className = "tree-folder";
  details.dataset.path = node.path;
  details.dataset.depth = String(depth);
  details.open = shouldFolderBeOpen(node.path);
  details.addEventListener("toggle", () => {
    if (details.open) expandedFolders.add(node.path);
    else if (node.path !== ".") expandedFolders.delete(node.path);
  });

  const summary = document.createElement("summary");
  summary.tabIndex = 0;

  const folderCheckbox = document.createElement("input");
  folderCheckbox.type = "checkbox";
  folderCheckbox.className = "tree-checkbox folder-check";
  folderCheckbox.dataset.folderPath = node.path;
  folderCheckbox.addEventListener("click", (e) => {
    e.stopPropagation();
  });
  folderCheckbox.addEventListener("change", () => {
    const filePaths = collectFilePaths(node);
    filePaths.forEach((path) => {
      if (folderCheckbox.checked) selectedFiles.add(path);
      else selectedFiles.delete(path);
    });
    renderTree();
    syncLockUi();
  });

  const label = document.createElement("span");
  label.className = "folder-label";
  label.innerHTML = [
    "<span class='folder-icon-wrap' aria-hidden='true'>",
    "  <svg class='folder-icon folder-icon-closed' viewBox='0 0 24 24' fill='none' aria-hidden='true'>",
    "    <path d='M3.5 7.5a2 2 0 0 1 2-2h4.2l1.7 1.9h7.1a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2v-9z' stroke='currentColor' stroke-width='1.6' stroke-linejoin='round'/>",
    "  </svg>",
    "  <svg class='folder-icon folder-icon-open' viewBox='0 0 24 24' fill='none' aria-hidden='true'>",
    "    <path d='M2.8 9.2a2 2 0 0 1 2-1.7h14.5a2 2 0 0 1 2 2.5l-1.2 5.6a2 2 0 0 1-2 1.6H5.3a2 2 0 0 1-2-2.4l.5-2.3' stroke='currentColor' stroke-width='1.6' stroke-linejoin='round'/>",
    "    <path d='M9.5 5.5 11.1 7h2.9' stroke='currentColor' stroke-width='1.6' stroke-linecap='round'/>",
    "  </svg>",
    "</span>",
    `<span>${escapeHtml(node.name)}</span>`,
  ].join("");

  summary.appendChild(folderCheckbox);
  summary.appendChild(label);
  details.appendChild(summary);

  for (const child of node.children || []) details.appendChild(createNode(child, depth + 1));
  return details;
}

function collectFilePaths(node) {
  if (node.type === "file") return [node.path];
  const out = [];
  for (const child of node.children || []) out.push(...collectFilePaths(child));
  return out;
}

function refreshFolderCheckStates() {
  const checks = treeRoot.querySelectorAll(".folder-check");
  checks.forEach((check) => {
    const path = check.dataset.folderPath;
    const folderNode = findNodeByPath(treeData, path);
    if (!folderNode) return;
    const files = collectFilePaths(folderNode);
    const selectedCount = files.filter((p) => selectedFiles.has(p)).length;
    check.indeterminate = selectedCount > 0 && selectedCount < files.length;
    check.checked = files.length > 0 && selectedCount === files.length;
  });
}

function findNodeByPath(node, path) {
  if (!node) return null;
  if (node.path === path) return node;
  if (node.type === "file") return null;
  for (const child of node.children || []) {
    const hit = findNodeByPath(child, path);
    if (hit) return hit;
  }
  return null;
}

async function selectFile(button) {
  const path = button.dataset.path;
  const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`);
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    setStatus(body.error || "Failed to load file", "error");
    return;
  }
  if (selectedFileNode) selectedFileNode.classList.remove("selected");
  selectedFileNode = button;
  selectedFileNode.classList.add("selected");
  selectedPathValue = path;
  selectedPath.value = body.path;
  document.getElementById("titleInput").value = body.tags.TITLE || "";
  document.getElementById("artistInput").value = body.tags.ARTIST || "";
  document.getElementById("albumInput").value = body.tags.ALBUM || "";
  document.getElementById("albumArtistInput").value = body.tags.ALBUMARTIST || "";
  document.getElementById("trackInput").value = body.tags.TRACKNUMBER || "";
  document.getElementById("genreInput").value = body.tags.GENRE || "";
  document.getElementById("yearInput").value = body.tags.YEAR || "";
  document.getElementById("discInput").value = body.tags.DISCNUMBER || "";
  coverPreview.src = body.tags.cover_data_url || placeholderCover;
  syncPlayerMeta(body.tags, body.path);
  treeCoverCache.set(path, body.tags.cover_data_url || null);
  audioPreview.src = `/api/audio?path=${encodeURIComponent(path)}`;
  if (!selectedFiles.has(path)) {
    selectedFiles.clear();
    selectedFiles.add(path);
  }
  setStatus(`Loaded ${body.path}`);
  syncLockUi();
  refreshFolderCheckStates();
}

function shouldFolderBeOpen(path) {
  if (path === ".") return true;
  if (expandedFolders.has(path)) return true;
  if (selectedPathValue && isAncestorOf(path, selectedPathValue)) return true;
  if (treeFilter) return true;
  return false;
}

function isAncestorOf(folderPath, filePath) {
  if (folderPath === ".") return true;
  return filePath.startsWith(`${folderPath}/`) || filePath === folderPath;
}

function rebindSelectedNode() {
  if (selectedFiles.size === 0 && !selectedPath.value && !selectedPathValue) {
    clearSelectedTrackUi();
    syncLockUi();
    return;
  }
  if (!selectedPathValue) {
    selectedFileNode = null;
    syncLockUi();
    return;
  }
  const node = treeRoot.querySelector(`.file-node[data-path="${cssEscape(selectedPathValue)}"]`);
  if (node) {
    selectedFileNode = node;
    selectedFileNode.classList.add("selected");
  } else selectedFileNode = null;
  syncLockUi();
}

function filterTree(node, query) {
  const q = query.trim().toLowerCase();
  if (!q) return node;
  if (node.type === "file") return node.name.toLowerCase().includes(q) ? node : null;
  const children = (node.children || []).map((child) => filterTree(child, q)).filter(Boolean);
  const folderMatch = node.name.toLowerCase().includes(q);
  if (folderMatch || children.length > 0 || node.path === ".") return { ...node, children };
  return null;
}

function escapeHtml(value) {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function cssEscape(value) {
  if (window.CSS && typeof window.CSS.escape === "function") return window.CSS.escape(value);
  return value.replace(/["\\]/g, "\\$&");
}

function applyTheme(themeName) {
  const allowedThemes = new Set(["purple", "ocean", "emerald", "sunset"]);
  const nextTheme = allowedThemes.has(themeName) ? themeName : "purple";
  document.documentElement.setAttribute("data-theme", nextTheme);
  if (themeSelect && themeSelect.value !== nextTheme) themeSelect.value = nextTheme;
  localStorage.setItem(themeStorageKey, nextTheme);
}

async function loadTreeCover(path) {
  if (treeCoverCache.has(path)) return treeCoverCache.get(path);
  if (treeCoverPending.has(path)) return treeCoverPending.get(path);
  const pending = fetch(`/api/file?path=${encodeURIComponent(path)}`)
    .then(async (res) => {
      const body = await parseJsonSafe(res);
      const cover = res.ok ? (body.tags?.cover_data_url || null) : null;
      treeCoverCache.set(path, cover);
      treeCoverPending.delete(path);
      return cover;
    })
    .catch(() => {
      treeCoverCache.set(path, null);
      treeCoverPending.delete(path);
      return null;
    });
  treeCoverPending.set(path, pending);
  return pending;
}

async function hydrateTreeThumb(button) {
  const thumb = button.querySelector(".tree-thumb");
  const img = button.querySelector(".tree-thumb-img");
  const fallback = button.querySelector(".tree-thumb-fallback");
  const path = button.dataset.path;
  if (!thumb || !img || !fallback || !path) return;
  const cover = await loadTreeCover(path);
  if (!button.isConnected) return;
  if (cover) {
    img.src = cover;
    img.classList.remove("hidden");
    fallback.classList.add("hidden");
    thumb.classList.add("has-image");
    return;
  }
  img.removeAttribute("src");
  img.classList.add("hidden");
  fallback.classList.remove("hidden");
  thumb.classList.remove("has-image");
}

function initializeTreeThumbnails() {
  if (treeThumbObserver) treeThumbObserver.disconnect();
  treeThumbObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      const button = entry.target;
      treeThumbObserver.unobserve(button);
      hydrateTreeThumb(button).catch(() => {});
    });
  }, {
    root: treeRoot,
    threshold: 0.05,
    rootMargin: "120px 0px",
  });
  treeRoot.querySelectorAll(".file-node[data-path]").forEach((button) => treeThumbObserver.observe(button));
}

function isCompactTreeLayout() {
  return treeCompactMedia.matches;
}

function clampTreeWidth(width) {
  const min = 240;
  const max = Math.min(680, Math.floor(window.innerWidth * 0.65));
  if (!Number.isFinite(width)) return min;
  return Math.max(min, Math.min(max, width));
}

function setTreeWidth(width, persist = false) {
  if (isCompactTreeLayout()) return;
  const clamped = clampTreeWidth(width);
  document.documentElement.style.setProperty("--tree-width", `${clamped}px`);
  if (persist) localStorage.setItem(treeWidthStorageKey, String(clamped));
}

function loadTreeWidthPreference() {
  const raw = Number.parseInt(localStorage.getItem(treeWidthStorageKey) || "", 10);
  if (Number.isFinite(raw)) {
    setTreeWidth(raw, false);
  }
}

function endTreeResize() {
  if (!treeResizeSession) return;
  document.body.style.userSelect = "";
  treeResizeHandle.classList.remove("dragging");
  treeResizeHandle.releasePointerCapture?.(treeResizeSession.pointerId);
  treeResizeSession = null;
}

function onTreeResizePointerDown(event) {
  if (!treeResizeHandle || isCompactTreeLayout()) return;
  const current = getComputedStyle(document.documentElement).getPropertyValue("--tree-width").trim();
  const startWidth = Number.parseFloat(current) || 320;
  treeResizeSession = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startWidth,
  };
  treeResizeHandle.classList.add("dragging");
  treeResizeHandle.setPointerCapture?.(event.pointerId);
  document.body.style.userSelect = "none";
  event.preventDefault();
}

function onTreeResizePointerMove(event) {
  if (!treeResizeSession || event.pointerId !== treeResizeSession.pointerId) return;
  const delta = event.clientX - treeResizeSession.startX;
  setTreeWidth(treeResizeSession.startWidth + delta, false);
}

function onTreeResizePointerUp(event) {
  if (!treeResizeSession || event.pointerId !== treeResizeSession.pointerId) return;
  const current = getComputedStyle(document.documentElement).getPropertyValue("--tree-width").trim();
  const width = Number.parseFloat(current) || treeResizeSession.startWidth;
  setTreeWidth(width, true);
  endTreeResize();
}

function onTreeLayoutChange() {
  if (isCompactTreeLayout()) {
    document.documentElement.style.removeProperty("--tree-width");
    endTreeResize();
    return;
  }
  loadTreeWidthPreference();
}

function initializeTreeResize() {
  if (!treeResizeHandle) return;
  treeResizeHandle.addEventListener("pointerdown", onTreeResizePointerDown);
  treeResizeHandle.addEventListener("pointermove", onTreeResizePointerMove);
  treeResizeHandle.addEventListener("pointerup", onTreeResizePointerUp);
  treeResizeHandle.addEventListener("pointercancel", endTreeResize);
  treeCompactMedia.addEventListener("change", onTreeLayoutChange);
  onTreeLayoutChange();
}

async function toggleLock() {
  const res = await fetch("/api/lock", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify({ unlocked: !unlocked }),
  });
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    setStatus(body.error || "Unable to update lock state", "error");
    return;
  }
  unlocked = body.unlocked;
  setStatus(unlocked ? "Unlocked: editing enabled." : "Locked: editing disabled.");
  syncLockUi();
}

function getBulkPayloadFromForm() {
  const formData = new FormData(tagForm);
  return {
    TITLE: formData.get("TITLE") || "",
    ARTIST: formData.get("ARTIST") || "",
    ALBUM: formData.get("ALBUM") || "",
    ALBUMARTIST: formData.get("ALBUMARTIST") || "",
    TRACKNUMBER: formData.get("TRACKNUMBER") || "",
    GENRE: formData.get("GENRE") || "",
    YEAR: formData.get("YEAR") || "",
    DISCNUMBER: formData.get("DISCNUMBER") || "",
  };
}

function getCheckedApplyFields() {
  const fields = [];
  bulkApplyCheckboxes.forEach((checkbox) => {
    if (!checkbox.disabled && !checkbox.classList.contains("hidden") && checkbox.checked) {
      fields.push(checkbox.dataset.tag);
    }
  });
  return fields;
}

async function saveSingle(formData) {
  const res = await fetch("/api/save", {
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: formData,
  });
  return parseJsonSafe(res).then((body) => ({ ok: res.ok, body }));
}

async function saveBulk() {
  const payload = getBulkPayloadFromForm();
  const applyFields = getCheckedApplyFields();
  if (applyFields.length === 0) {
    return { ok: false, body: { error: "Check at least one tag to apply in bulk mode." } };
  }
  payload.paths = Array.from(selectedFiles);
  payload.bulk_mode = bulkMode;
  payload.apply_fields = applyFields;
  payload.TITLE = "";
  if (bulkMode === "compilation") {
    payload.ARTIST = "";
    payload.TRACKNUMBER = "";
    payload.DISCNUMBER = "";
  }
  const res = await fetch("/api/save-bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify(payload),
  });
  return parseJsonSafe(res).then((body) => ({ ok: res.ok, body }));
}

async function postBulkCoverSet(paths, coverFile, missingFileError) {
  if (!coverFile) {
    return { ok: false, body: { error: missingFileError || "Choose an image file first." } };
  }
  const formData = new FormData();
  formData.append("mode", "set");
  formData.append("paths", JSON.stringify(paths));
  formData.append("cover", coverFile);
  const res = await fetch("/api/cover-bulk", {
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: formData,
  });
  const body = await parseJsonSafe(res);
  return { ok: res.ok, body };
}

async function saveBulkCover(paths) {
  return postBulkCoverSet(paths, coverInput.files[0], "Choose an image file for bulk cover update.");
}

async function postJson(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
    body: JSON.stringify(payload),
  });
  const body = await parseJsonSafe(res);
  return { ok: res.ok, body };
}

async function loadPresets() {
  const res = await fetch("/api/presets");
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    setStatus(body.error || "Failed loading presets", "error");
    return;
  }
  presetSelect.innerHTML = "";
  (body.presets || []).forEach((preset) => {
    const option = document.createElement("option");
    option.value = preset.name;
    option.textContent = preset.name;
    option.dataset.values = JSON.stringify(preset.values || {});
    presetSelect.appendChild(option);
  });
  setStatus(`Loaded ${body.presets?.length || 0} presets.`);
}

async function previewParser() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files to parse first.", "error");
    return;
  }
  const { ok, body } = await postJson("/api/parser-preview", { paths, pattern: parserPattern.value });
  if (!ok) {
    setStatus(body.error || "Parser preview failed", "error");
    return;
  }
  const sample = (body.preview || []).slice(0, 2).map((x) => `${x.path} -> ${JSON.stringify(x.proposed)}`).join(" | ");
  setStatus(sample || "Parser preview generated.");
}

async function applyParser() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files to parse first.", "error");
    return;
  }
  const { ok, body } = await postJson("/api/parser-preview", { paths, pattern: parserPattern.value });
  if (!ok) {
    setStatus(body.error || "Parser failed", "error");
    return;
  }
  const updates = (body.preview || []).map((item) => ({ path: item.path, fields: item.proposed || {} }));
  const result = await postJson("/api/apply-map", { updates });
  if (!result.ok) {
    setStatus(result.body.error || "Apply parser failed", "error");
    return;
  }
  setStatus(`Parser applied: ${result.body.updated} updated, ${result.body.failed_count} failed.`, result.body.failed_count ? "error" : "success");
}

async function savePreset() {
  const name = (presetNameInput.value || "").trim();
  if (!name) {
    setStatus("Preset name is required.", "error");
    return;
  }
  const values = getBulkPayloadFromForm();
  const { ok, body } = await postJson("/api/presets", { action: "save", name, values });
  if (!ok) {
    setStatus(body.error || "Failed to save preset", "error");
    return;
  }
  await loadPresets();
  setStatus("Preset saved.", "success");
}

async function applyPreset() {
  const option = presetSelect.options[presetSelect.selectedIndex];
  if (!option) {
    setStatus("Load and select a preset first.", "error");
    return;
  }
  const values = JSON.parse(option.dataset.values || "{}");
  const payload = getBulkPayloadFromForm();
  Object.keys(values).forEach((k) => {
    payload[k] = values[k];
  });
  payload.paths = getActivePaths();
  if (!payload.paths.length) {
    setStatus("Select files/folders first.", "error");
    return;
  }
  payload.TITLE = "";
  payload.ARTIST = "";
  const result = await postJson("/api/save-bulk", payload);
  if (!result.ok) {
    setStatus(result.body.error || "Preset apply failed", "error");
    return;
  }
  setStatus(`Preset applied: ${result.body.updated} updated, ${result.body.failed_count} failed.`, result.body.failed_count ? "error" : "success");
}

async function previewOrApplyNumbering(apply) {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files for numbering first.", "error");
    return;
  }
  const { ok, body } = await postJson("/api/auto-number", {
    paths,
    start: 1,
    pad: 2,
    reset_per_folder: true,
    apply,
  });
  if (!ok) {
    setStatus(body.error || "Auto numbering failed", "error");
    return;
  }
  if (!apply) {
    const sample = (body.preview || []).slice(0, 3).map((x) => `${x.path} -> ${x.TRACKNUMBER}`).join(" | ");
    setStatus(sample || "Numbering preview ready.");
    return;
  }
  setStatus(`Numbering applied: ${body.updated} updated, ${body.failed_count} failed.`, body.failed_count ? "error" : "success");
}

async function previewBulkDiff() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files first.", "error");
    return;
  }
  const payload = getBulkPayloadFromForm();
  payload.paths = paths;
  payload.TITLE = "";
  payload.ARTIST = "";
  const result = await postJson("/api/preview-bulk", payload);
  if (!result.ok) {
    setStatus(result.body.error || "Bulk preview failed", "error");
    return;
  }
  const changed = (result.body.preview || []).filter((x) => !x.error).length;
  setStatus(`Preview generated for ${changed} files.`);
}

async function undoLastOperation() {
  const result = await postJson("/api/undo-last", {});
  if (!result.ok) {
    setStatus(result.body.error || "Undo failed", "error");
    return;
  }
  setStatus(`Undo complete: ${result.body.updated} restored, ${result.body.failed_count} failed.`, result.body.failed_count ? "error" : "success");
}

async function qualityCheck() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files first.", "error");
    return;
  }
  const result = await postJson("/api/quality-check", { paths });
  if (!result.ok) {
    setStatus(result.body.error || "Quality check failed", "error");
    return;
  }
  const issues = result.body.issues || [];
  setStatus(`Quality check found ${issues.length} issues.`);
}

async function bulkRemoveCovers() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files first.", "error");
    return;
  }
  const formData = new FormData();
  formData.append("mode", "remove");
  formData.append("paths", JSON.stringify(paths));
  const res = await fetch("/api/cover-bulk", {
    method: "POST",
    headers: { "X-CSRFToken": getCsrfToken() },
    body: formData,
  });
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    setStatus(body.error || "Bulk cover remove failed", "error");
    return;
  }
  setStatus(`Cover update: ${body.updated} updated, ${body.failed_count} failed.`, body.failed_count ? "error" : "success");
}

async function bulkSetCover() {
  const paths = getActivePaths();
  if (!paths.length) {
    setStatus("Select files first.", "error");
    return;
  }
  const { ok, body } = await postBulkCoverSet(paths, bulkCoverInput.files[0], "Choose an image file first.");
  if (!ok) {
    setStatus(body.error || "Bulk cover set failed", "error");
    return;
  }
  setStatus(`Cover update: ${body.updated} updated, ${body.failed_count} failed.`, body.failed_count ? "error" : "success");
}

async function lookupMetadata() {
  const artist = (lookupArtistInput.value || "").trim();
  const album = (lookupAlbumInput.value || "").trim();
  const qs = new URLSearchParams();
  if (artist) qs.set("artist", artist);
  if (album) qs.set("album", album);
  const res = await fetch(`/api/lookup?${qs.toString()}`);
  const body = await parseJsonSafe(res);
  if (!res.ok) {
    lookupResults.textContent = body.error || "Lookup failed";
    return;
  }
  lookupResults.textContent = JSON.stringify(body.suggestions || [], null, 2);
}

async function saveTags(event) {
  event.preventDefault();
  if (selectedFiles.size === 0 && !selectedPath.value) {
    setStatus("Select at least one music file first.", "error");
    return;
  }

  const bulk = isBulkMode();
  if (bulk) {
    const applyFields = getCheckedApplyFields();
    const applyCover = Boolean(bulkCoverApplyCheckbox?.checked);
    if (!applyFields.length && !applyCover) {
      setStatus("Check at least one tag or COVER to apply in bulk mode.", "error");
      return;
    }
    startSaveProgress("Saving bulk changes...");
    const paths = Array.from(selectedFiles);
    const summaries = [];
    let hadFailure = false;

    if (applyFields.length) {
      const { ok, body } = await saveBulk();
      if (!ok) {
        finishSaveProgress(false, "Bulk save failed.");
        setStatus(body.error || "Bulk save failed", "error");
        return;
      }
      const previewErrors = (body.failed || []).slice(0, 2).map((x) => `${x.path}: ${x.error}`).join(" | ");
      summaries.push(`Tags: ${body.updated} updated, ${body.failed_count} failed.`);
      if (previewErrors) summaries.push(previewErrors);
      if (body.failed_count) hadFailure = true;
    }

    if (applyCover) {
      const coverResult = await saveBulkCover(paths);
      if (!coverResult.ok) {
        finishSaveProgress(false, "Bulk cover failed.");
        setStatus(coverResult.body.error || "Bulk cover update failed", "error");
        return;
      }
      summaries.push(`Cover: ${coverResult.body.updated} updated, ${coverResult.body.failed_count} failed.`);
      if (coverResult.body.failed_count) hadFailure = true;
    }

    finishSaveProgress(true, "Bulk changes saved.");
    coverInput.value = "";
    setStatus(summaries.join(" "), hadFailure ? "error" : "success");
    return;
  }

  const formData = new FormData(tagForm);
  startSaveProgress("Saving track changes...");
  if (coverInput.files[0]) formData.append("cover", coverInput.files[0]);
  const { ok, body } = await saveSingle(formData);
  if (!ok) {
    finishSaveProgress(false, "Save failed.");
    setStatus(body.error || "Failed to save metadata", "error");
    return;
  }
  finishSaveProgress(true, "Track saved.");
  coverInput.value = "";
  setStatus("Changes saved.", "success");
}

lockBtn.addEventListener("click", toggleLock);
toolsCloseBtn.addEventListener("click", () => setToolsOpen(false));
toolsBackdrop.addEventListener("click", () => setToolsOpen(false));
reloadTreeBtn.addEventListener("click", () => fetchTree().catch((err) => setStatus(err.message, "error")));
treeFilterInput.addEventListener("input", (event) => {
  treeFilter = event.target.value || "";
  renderTree();
});
tagForm.addEventListener("submit", saveTags);
previewParserBtn.addEventListener("click", previewParser);
applyParserBtn.addEventListener("click", applyParser);
savePresetBtn.addEventListener("click", savePreset);
loadPresetsBtn.addEventListener("click", loadPresets);
applyPresetBtn.addEventListener("click", applyPreset);
previewNumberBtn.addEventListener("click", () => previewOrApplyNumbering(false));
applyNumberBtn.addEventListener("click", () => previewOrApplyNumbering(true));
previewBulkBtn.addEventListener("click", previewBulkDiff);
undoLastBtn.addEventListener("click", undoLastOperation);
qualityCheckBtn.addEventListener("click", qualityCheck);
removeCoverBulkBtn.addEventListener("click", bulkRemoveCovers);
setCoverBulkBtn.addEventListener("click", bulkSetCover);
lookupBtn.addEventListener("click", lookupMetadata);
bulkModeCompilationBtn.addEventListener("click", () => setBulkMode("compilation"));
bulkModeTemplateBtn.addEventListener("click", () => setBulkMode("template"));
bulkApplyCheckboxes.forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    const row = checkbox.closest(".tag-field");
    if (row) row.classList.toggle("unchecked", !checkbox.checked);
  });
});
bulkCoverApplyCheckbox?.addEventListener("change", syncLockUi);
themeSelect?.addEventListener("change", (event) => applyTheme(event.target.value));
playerBackBtn?.addEventListener("click", () => navigateTrack(-1).catch(() => {}));
playerForwardBtn?.addEventListener("click", () => navigateTrack(1).catch(() => {}));
playerPlayPauseBtn?.addEventListener("click", async () => {
  if (!audioPreview.src) return;
  if (audioPreview.paused) {
    try {
      await audioPreview.play();
    } catch {
      setStatus("Unable to start playback.", "error");
    }
  } else {
    audioPreview.pause();
  }
  syncPlayerButtonLabel();
});
playerSeek?.addEventListener("input", () => {
  playerIsSeeking = true;
  const duration = Number.isFinite(audioPreview.duration) ? audioPreview.duration : 0;
  const next = (Number(playerSeek.value) / 1000) * duration;
  playerCurrentTime.textContent = formatTime(next);
});
playerSeek?.addEventListener("change", () => {
  const duration = Number.isFinite(audioPreview.duration) ? audioPreview.duration : 0;
  audioPreview.currentTime = duration > 0 ? (Number(playerSeek.value) / 1000) * duration : 0;
  playerIsSeeking = false;
  syncPlayerProgress();
});
playerVolume?.addEventListener("input", () => {
  audioPreview.volume = Number(playerVolume.value);
});
audioPreview.addEventListener("loadedmetadata", syncPlayerProgress);
audioPreview.addEventListener("timeupdate", syncPlayerProgress);
audioPreview.addEventListener("play", syncPlayerButtonLabel);
audioPreview.addEventListener("pause", syncPlayerButtonLabel);
audioPreview.addEventListener("ended", syncPlayerButtonLabel);
audioPreview.addEventListener("volumechange", () => {
  if (!playerVolume) return;
  playerVolume.value = String(audioPreview.volume);
});
document.addEventListener("keydown", (event) => {
  if (isTypingTarget(event.target)) {
    if (event.key === "Escape" && isToolsOpen) setToolsOpen(false);
    return;
  }
  if (!isBulkMode()) {
    if (event.key === " " && audioPreview.src) {
      event.preventDefault();
      playerPlayPauseBtn?.click();
      return;
    }
    if (event.key === "ArrowLeft" && audioPreview.src) {
      event.preventDefault();
      playerBackBtn?.click();
      return;
    }
    if (event.key === "ArrowRight" && audioPreview.src) {
      event.preventDefault();
      playerForwardBtn?.click();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      audioPreview.volume = Math.min(1, audioPreview.volume + 0.05);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      audioPreview.volume = Math.max(0, audioPreview.volume - 0.05);
      return;
    }
  }
  if (event.key === "Escape" && isToolsOpen) {
    setToolsOpen(false);
  }
});

treeRoot.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== "checkbox") return;
  if (selectedFiles.size === 0) {
    clearSelectedTrackUi();
    setStatus("Selection cleared.");
    syncLockUi();
  }
});

syncLockUi();
syncPlayerMeta();
syncPlayerButtonLabel();
syncPlayerProgress();
if (playerVolume) playerVolume.value = String(audioPreview.volume);
applyTheme(localStorage.getItem(themeStorageKey) || "purple");
initializeTreeResize();
setToolsOpen(isToolsOpen);
coverPreview.src = placeholderCover;
fetchTree().catch((err) => setStatus(err.message, "error"));
loadPresets().catch(() => {});
