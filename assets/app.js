/* 每日時事統整 — 前端邏輯（vanilla JS，無建置步驟） */

const CATEGORY_LABEL = { finance: "金融", ai: "AI科技", investment: "投資" };
const REGION_LABEL = { taiwan: "台灣", international: "國際" };
const BM_KEY = "news_bookmarks_v1"; // localStorage：{ id: itemSnapshot }

const state = {
  items: [],
  filterCategory: "all",
  filterRegion: "all",
  view: "all", // all | bookmarks
};

/* ───── localStorage 收藏 ───── */
function loadBookmarks() {
  try {
    return JSON.parse(localStorage.getItem(BM_KEY)) || {};
  } catch {
    return {};
  }
}
function saveBookmarks(bm) {
  localStorage.setItem(BM_KEY, JSON.stringify(bm));
}
function isBookmarked(id) {
  return Object.prototype.hasOwnProperty.call(loadBookmarks(), id);
}
function toggleBookmark(item) {
  const bm = loadBookmarks();
  if (bm[item.id]) {
    delete bm[item.id];
  } else {
    // 連同最小內容一起存，新聞輪替後收藏仍可顯示
    bm[item.id] = {
      id: item.id, title: item.title, url: item.url, source: item.source,
      category: item.category, region: item.region,
      summary: item.summary, insight: item.insight, published: item.published,
    };
  }
  saveBookmarks(bm);
}

/* ───── 工具 ───── */
function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d)) return "";
  return d.toLocaleDateString("zh-TW", { month: "2-digit", day: "2-digit" }) +
    " " + d.toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" });
}
function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : s;
  return div.innerHTML;
}

/* ───── 渲染 ───── */
function currentList() {
  if (state.view === "bookmarks") {
    const bm = loadBookmarks();
    // 優先使用最新清單中的版本，否則用收藏快照（標記 stale）
    return Object.values(bm).map((snap) => {
      const live = state.items.find((it) => it.id === snap.id);
      return live ? live : { ...snap, _stale: true };
    });
  }
  return state.items;
}

function applyFilters(list) {
  return list.filter((it) =>
    (state.filterCategory === "all" || it.category === state.filterCategory) &&
    (state.filterRegion === "all" || it.region === state.filterRegion)
  );
}

function cardHTML(item, i = 0) {
  const active = isBookmarked(item.id) ? "active" : "";
  const stale = item._stale
    ? `<span class="stale">· 已不在最新清單</span>` : "";
  const insight = item.insight
    ? `<div class="insight"><strong>Insight</strong>${esc(item.insight)}</div>` : "";
  const delay = Math.min(i, 12) * 45; // 進場 stagger（上限避免太久）
  return `
    <article class="card" style="animation-delay:${delay}ms">
      <button class="star-btn ${active}" data-id="${esc(item.id)}" title="收藏" aria-label="收藏">★</button>
      <div class="card-tags">
        <span class="tag cat">${esc(CATEGORY_LABEL[item.category] || item.category)}</span>
        <span class="tag region">${esc(REGION_LABEL[item.region] || item.region)}</span>
      </div>
      <h2 class="card-title">
        <a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">${esc(item.title)}</a>
      </h2>
      ${item.summary ? `<p class="card-summary">${esc(item.summary)}</p>` : ""}
      ${insight}
      <div class="card-meta">
        <a href="${esc(item.url)}" target="_blank" rel="noopener noreferrer">來源：${esc(item.source)} ↗</a>
        <span>${fmtDate(item.published)} ${stale}</span>
      </div>
    </article>`;
}

function render() {
  const list = applyFilters(currentList());
  const container = document.getElementById("news-list");
  const empty = document.getElementById("empty-state");

  container.innerHTML = list.map((item, i) => cardHTML(item, i)).join("");
  empty.hidden = list.length > 0;
  document.getElementById("bm-count").textContent = Object.keys(loadBookmarks()).length;

  // 綁定收藏星號
  container.querySelectorAll(".star-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.getAttribute("data-id");
      const item = currentList().find((it) => it.id === id) ||
        state.items.find((it) => it.id === id);
      if (item) {
        toggleBookmark(item);
        render();
      }
    });
  });
}

/* ───── 事件 ───── */
function wireControls() {
  document.getElementById("filter-category").addEventListener("change", (e) => {
    state.filterCategory = e.target.value;
    render();
  });
  document.getElementById("filter-region").addEventListener("change", (e) => {
    state.filterRegion = e.target.value;
    render();
  });
  document.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".toggle-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      state.view = btn.getAttribute("data-view");
      render();
    });
  });
}

/* ───── 手機篩選收合（JS 控制，避免 CSS 權重問題） ───── */
const MOBILE_BP = 768;

function applyMobileHeader() {
  const btn = document.getElementById("filter-toggle");
  const bar = document.getElementById("controls-bar");
  if (!btn || !bar) return;

  if (window.innerWidth <= MOBILE_BP) {
    // 手機：顯示篩選按鈕，預設收起篩選列
    btn.style.display = "flex";
    if (!bar.classList.contains("open")) {
      bar.style.display = "none";
    }
  } else {
    // 桌機：隱藏篩選按鈕，永遠顯示篩選列
    btn.style.display = "none";
    bar.style.display = "";
    bar.classList.remove("open");
    btn.classList.remove("active");
  }
}

function wireFilterToggle() {
  const btn = document.getElementById("filter-toggle");
  const bar = document.getElementById("controls-bar");
  if (!btn || !bar) return;

  btn.addEventListener("click", () => {
    const opening = !bar.classList.contains("open");
    bar.classList.toggle("open", opening);
    bar.style.display = opening ? "flex" : "none";
    btn.classList.toggle("active", opening);
  });

  applyMobileHeader();
  window.addEventListener("resize", applyMobileHeader);
}

/* ───── 啟動 ───── */
async function init() {
  wireControls();
  wireFilterToggle();
  const updated = document.getElementById("updated");
  try {
    const res = await fetch("data/latest.json", { cache: "no-store" });
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    state.items = data.items || [];
    updated.textContent = data.updated_at
      ? "更新於 " + fmtDate(data.updated_at)
      : "";
  } catch (err) {
    updated.textContent = "無法載入資料";
    console.error("載入 latest.json 失敗：", err);
  }
  render();
}

document.addEventListener("DOMContentLoaded", init);
