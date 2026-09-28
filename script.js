/* ============================================================
   Recipe Box — mini project
   Data source: TheMealDB free public API (test key "1")
   Accounts + favorites: Flask/SQLite backend (/api/*); falls back to
   browser localStorage when no backend is available or nobody is logged in.
   Docs: https://www.themealdb.com/api.php
   ============================================================ */
 
const API_BASE = "https://www.themealdb.com/api/json/v1/1";
 
// ---- DOM refs ----
const form = document.getElementById("search-form");
const input = document.getElementById("search-input");
const modeButtons = document.querySelectorAll(".mode-btn");
const surpriseBtn = document.getElementById("surprise-btn");
const tagButtons = document.querySelectorAll(".tag");
const resultsTitle = document.getElementById("results-title");
const grid = document.getElementById("results-grid");
const statusEl = document.getElementById("status");
const emptyState = document.getElementById("empty-state");
const filterRow = document.getElementById("filter-row");
const categoryFilter = document.getElementById("category-filter");
const sortSelect = document.getElementById("sort-select");
const favToggle = document.getElementById("fav-toggle");
const favCount = document.getElementById("fav-count");
const favDrawer = document.getElementById("fav-drawer");
const favClose = document.getElementById("fav-close");
const favOverlay = document.getElementById("fav-overlay");
const favList = document.getElementById("fav-list");
const modal = document.getElementById("modal");
const modalOverlay = document.getElementById("modal-overlay");
const modalContent = document.getElementById("modal-content");
const modalClose = document.getElementById("modal-close");
 
// ---- State ----
let searchMode = "name"; // "name" | "ingredient"
let currentResults = []; // normalized list currently shown
let favorites = loadFavorites(); // guest favorites (localStorage) until a user logs in
let currentUser = null; // { username } when logged in
let backendAvailable = false; // false on static hosting (e.g. GitHub Pages)
 
// ============================================================
// Init
// ============================================================
updateFavCount();
renderFavList();
loadStarterResults();
initAuth();
 
// ============================================================
// Search mode toggle
// ============================================================
modeButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    modeButtons.forEach((b) => {
      b.classList.remove("is-active");
      b.setAttribute("aria-selected", "false");
    });
    btn.classList.add("is-active");
    btn.setAttribute("aria-selected", "true");
    searchMode = btn.dataset.mode;
    input.placeholder =
      searchMode === "name"
        ? "e.g. paneer tikka, chicken, tacos…"
        : "e.g. chicken, rice, spinach…";
  });
});
 
// ============================================================
// Search form
// ============================================================
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const query = input.value.trim();
  if (!query) return;
  runSearch(query);
});
 
tagButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    input.value = btn.dataset.query;
    runSearch(btn.dataset.query);
  });
});
 
surpriseBtn.addEventListener("click", async () => {
  setStatus("Pulling a card at random…");
  showSkeletons(1);
  try {
    const res = await fetch(`${API_BASE}/random.php`);
    const data = await res.json();
    const meals = data.meals || [];
    currentResults = meals.map(normalizeMeal);
    resultsTitle.textContent = "Today's random pick";
    filterRow.hidden = true;
    clearStatus();
    renderGrid(currentResults);
  } catch (err) {
    showError();
  }
});
 
// ============================================================
// Core search
// ============================================================
async function runSearch(query) {
  setStatus(`Searching for "${query}"…`);
  showSkeletons(6);
  filterRow.hidden = true;
  try {
    const endpoint =
      searchMode === "name"
        ? `${API_BASE}/search.php?s=${encodeURIComponent(query)}`
        : `${API_BASE}/filter.php?i=${encodeURIComponent(query)}`;
 
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error("Network error");
    const data = await res.json();
    const meals = data.meals || [];
 
    if (meals.length === 0) {
      currentResults = [];
      clearStatus();
      grid.innerHTML = "";
      emptyState.hidden = false;
      resultsTitle.textContent = `No results for "${query}"`;
      return;
    }
 
    emptyState.hidden = true;
    currentResults = meals.map(normalizeMeal);
    resultsTitle.textContent =
      searchMode === "name"
        ? `Results for "${query}"`
        : `Recipes with "${query}"`;
    clearStatus();
    setupCategoryFilter(currentResults);
    renderGrid(currentResults);
  } catch (err) {
    showError();
  }
}
 
function normalizeMeal(meal) {
  // /filter.php results have fewer fields than /search.php ones
  return {
    id: meal.idMeal,
    name: meal.strMeal,
    thumb: meal.strMealThumb,
    category: meal.strCategory || "",
    area: meal.strArea || "",
  };
}
 
// ============================================================
// Starter view (nice defaults instead of a blank page)
// ============================================================
async function loadStarterResults() {
  setStatus("Loading a few favorites…");
  showSkeletons(6);
  try {
    const res = await fetch(`${API_BASE}/search.php?s=chicken`);
    const data = await res.json();
    const meals = (data.meals || []).slice(0, 8).map(normalizeMeal);
    currentResults = meals;
    clearStatus();
    setupCategoryFilter(meals);
    renderGrid(meals);
  } catch (err) {
    clearStatus();
    grid.innerHTML = "";
  }
}
 
// ============================================================
// Rendering
// ============================================================
function renderGrid(list) {
  grid.innerHTML = "";
  if (list.length === 0) {
    emptyState.hidden = false;
    return;
  }
  emptyState.hidden = true;
 
  const frag = document.createDocumentFragment();
  list.forEach((meal) => {
    const card = document.createElement("article");
    card.className = "recipe-card";
    if (isFavorite(meal.id)) card.classList.add("is-fav");
 
    card.innerHTML = `
      <button class="card-fav ${isFavorite(meal.id) ? "is-fav" : ""}" aria-label="Save recipe" data-id="${meal.id}">♥</button>
      <img class="thumb" src="${meal.thumb}" alt="${escapeHtml(meal.name)}" loading="lazy" />
      <div class="card-body">
        <p class="card-tags">${[meal.category, meal.area].filter(Boolean).join(" · ") || "Recipe"}</p>
        <h3>${escapeHtml(meal.name)}</h3>
      </div>
    `;
 
    card.addEventListener("click", (e) => {
      if (e.target.closest(".card-fav")) return;
      openModal(meal.id);
    });
 
    card.querySelector(".card-fav").addEventListener("click", (e) => {
      e.stopPropagation();
      toggleFavorite(meal);
    });
 
    frag.appendChild(card);
  });
  grid.appendChild(frag);
}
 
function showSkeletons(count) {
  grid.innerHTML = "";
  emptyState.hidden = true;
  for (let i = 0; i < count; i++) {
    const s = document.createElement("div");
    s.className = "skeleton";
    s.innerHTML = `<div class="thumb"></div><div class="line"></div><div class="line short"></div>`;
    grid.appendChild(s);
  }
}
 
function setStatus(msg) {
  statusEl.hidden = false;
  statusEl.classList.remove("is-error");
  statusEl.textContent = msg;
}
function clearStatus() {
  statusEl.hidden = true;
  statusEl.textContent = "";
}
function showError() {
  clearStatus();
  grid.innerHTML = "";
  emptyState.hidden = false;
  document.querySelector(".empty-headline").textContent = "The connection dropped a plate.";
  document.querySelector(".empty-sub").textContent =
    "Something went wrong reaching the recipe database. Check your connection and try again.";
}
 
// ============================================================
// Category filter + sort (client-side, over currentResults)
// ============================================================
function setupCategoryFilter(list) {
  const categories = [...new Set(list.map((m) => m.category).filter(Boolean))].sort();
  if (categories.length <= 1) {
    filterRow.hidden = true;
    return;
  }
  filterRow.hidden = false;
  categoryFilter.innerHTML = `<option value="">All</option>` +
    categories.map((c) => `<option value="${c}">${c}</option>`).join("");
}
 
categoryFilter.addEventListener("change", applyFilters);
sortSelect.addEventListener("change", applyFilters);
 
function applyFilters() {
  let list = [...currentResults];
  const cat = categoryFilter.value;
  if (cat) list = list.filter((m) => m.category === cat);
 
  const sort = sortSelect.value;
  if (sort === "az") list.sort((a, b) => a.name.localeCompare(b.name));
  if (sort === "za") list.sort((a, b) => b.name.localeCompare(a.name));
 
  renderGrid(list);
}
 
// ============================================================
// Modal — full recipe detail
// ============================================================
async function openModal(id) {
  modal.hidden = false;
  modalOverlay.hidden = false;
  modal.setAttribute("aria-hidden", "false");
  modalContent.innerHTML = `<p style="padding:3rem 0;text-align:center;font-family:var(--font-mono);color:var(--text-muted)">Fetching the full card…</p>`;
 
  try {
    const res = await fetch(`${API_BASE}/lookup.php?i=${id}`);
    const data = await res.json();
    const meal = data.meals?.[0];
    if (!meal) throw new Error("Not found");
 
    const ingredients = [];
    for (let i = 1; i <= 20; i++) {
      const ing = meal[`strIngredient${i}`];
      const measure = meal[`strMeasure${i}`];
      if (ing && ing.trim()) {
        ingredients.push({ name: ing.trim(), amount: (measure || "").trim() });
      }
    }
 
    modalContent.innerHTML = `
      <img class="modal-img" src="${meal.strMealThumb}" alt="${escapeHtml(meal.strMeal)}" />
      <h2>${escapeHtml(meal.strMeal)}</h2>
      <p class="modal-meta">${[meal.strCategory, meal.strArea].filter(Boolean).join(" · ")}</p>
      <div class="modal-columns">
        <div>
          <h4>Ingredients</h4>
          <ul class="ingredient-list">
            ${ingredients
              .map((i) => `<li><span>${escapeHtml(i.name)}</span><span class="amt">${escapeHtml(i.amount)}</span></li>`)
              .join("")}
          </ul>
        </div>
        <div>
          <h4>Method</h4>
          <p class="instructions">${escapeHtml(meal.strInstructions || "No instructions provided.")}</p>
        </div>
      </div>
      ${meal.strYoutube ? `<a class="modal-link" href="${meal.strYoutube}" target="_blank" rel="noopener">Watch the video →</a>` : ""}
    `;
  } catch (err) {
    modalContent.innerHTML = `<p style="padding:3rem 0;text-align:center;">Couldn't load that recipe. Please try again.</p>`;
  }
}
 
function closeModal() {
  modal.hidden = true;
  modalOverlay.hidden = true;
  modal.setAttribute("aria-hidden", "true");
}
 
modalClose.addEventListener("click", closeModal);
modalOverlay.addEventListener("click", closeModal);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeModal();
    closeFavDrawer();
    closeAuthDialog();
  }
});
 
// ============================================================
// Favorites (database when logged in, localStorage as guest)
// ============================================================
function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem("recipeBoxFavorites")) || [];
  } catch {
    return [];
  }
}
function saveFavorites() {
  localStorage.setItem("recipeBoxFavorites", JSON.stringify(favorites));
}
function isFavorite(id) {
  return favorites.some((f) => f.id === id);
}
function toggleFavorite(meal) {
  return setFavorite(meal, !isFavorite(meal.id));
}
// Optimistic update; when logged in the change is also saved to the database.
async function setFavorite(meal, shouldBeFav) {
  const before = favorites;
  favorites = shouldBeFav
    ? isFavorite(meal.id) ? favorites : [...favorites, meal]
    : favorites.filter((f) => f.id !== meal.id);
  refreshFavoriteUI();
  if (!currentUser) {
    saveFavorites();
    return;
  }
  try {
    if (shouldBeFav) {
      await api("/api/favorites", { method: "POST", body: meal });
    } else {
      await api(`/api/favorites/${encodeURIComponent(meal.id)}`, { method: "DELETE" });
    }
  } catch (err) {
    favorites = before; // roll back the optimistic change
    refreshFavoriteUI();
    setStatus(err.message || "Couldn't update your favorites — please try again.");
  }
}
// Re-sync every place that shows favorite state (count, drawer, card hearts).
function refreshFavoriteUI() {
  updateFavCount();
  renderFavList();
  document.querySelectorAll(".card-fav").forEach((btn) => {
    const on = isFavorite(btn.dataset.id);
    btn.classList.toggle("is-fav", on);
    btn.closest(".recipe-card")?.classList.toggle("is-fav", on);
  });
}
function updateFavCount() {
  favCount.textContent = favorites.length;
}
function renderFavList() {
  if (favorites.length === 0) {
    favList.innerHTML = `<p class="fav-empty">No cards pinned yet. Tap the ♥ on any recipe to save it here.</p>`;
    return;
  }
  favList.innerHTML = favorites
    .map(
      (f) => `
      <div class="fav-item" data-id="${escapeAttr(f.id)}">
        <img src="${escapeAttr(f.thumb)}" alt="" />
        <span>${escapeHtml(f.name)}</span>
        <button data-remove="${escapeAttr(f.id)}" aria-label="Remove">×</button>
      </div>`
    )
    .join("");
 
  favList.querySelectorAll(".fav-item").forEach((item) => {
    item.addEventListener("click", (e) => {
      if (e.target.closest("button")) return;
      openModal(item.dataset.id);
    });
  });
  favList.querySelectorAll("[data-remove]").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const meal = favorites.find((f) => f.id === btn.dataset.remove);
      if (meal) setFavorite(meal, false);
    });
  });
}
 
favToggle.addEventListener("click", () => {
  const isOpen = favDrawer.classList.toggle("is-open");
  favOverlay.hidden = !isOpen;
  favToggle.setAttribute("aria-expanded", String(isOpen));
});
favClose.addEventListener("click", closeFavDrawer);
favOverlay.addEventListener("click", closeFavDrawer);
function closeFavDrawer() {
  favDrawer.classList.remove("is-open");
  favOverlay.hidden = true;
  favToggle.setAttribute("aria-expanded", "false");
}
 
// ============================================================
// Utils
// ============================================================
function escapeHtml(str = "") {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
function escapeAttr(str = "") {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ============================================================
// Backend API helper + accounts
// ============================================================
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response (e.g. static host without a backend) */
  }
  if (!res.ok || data === null) {
    throw new Error((data && data.error) || "Server unavailable.");
  }
  return data;
}

const accountBar = document.getElementById("account-bar");
const accountName = document.getElementById("account-name");
const accountBtn = document.getElementById("account-btn");
const authOverlay = document.getElementById("auth-overlay");
const authDialog = document.getElementById("auth-dialog");
const authClose = document.getElementById("auth-close");
const authForm = document.getElementById("auth-form");
const authTitle = document.getElementById("auth-title");
const authUsername = document.getElementById("auth-username");
const authPassword = document.getElementById("auth-password");
const authError = document.getElementById("auth-error");
const authSubmit = document.getElementById("auth-submit");
const authSwitchText = document.getElementById("auth-switch-text");
const authSwitch = document.getElementById("auth-switch");
let authMode = "login"; // "login" | "register"

async function initAuth() {
  try {
    const { user } = await api("/api/me");
    backendAvailable = true;
    accountBar.hidden = false;
    if (user) await onLoggedIn(user, false);
    else renderAccountBar();
  } catch {
    backendAvailable = false; // static hosting: stay in guest/localStorage mode
    accountBar.hidden = true;
  }
}

function renderAccountBar() {
  if (currentUser) {
    accountName.textContent = `Hi, ${currentUser.username}`;
    accountName.hidden = false;
    accountBtn.textContent = "Log out";
  } else {
    accountName.hidden = true;
    accountBtn.textContent = "Log in";
  }
}

// After login/register: move any guest favorites into the account, then load from the database.
async function onLoggedIn(user, mergeGuest = true) {
  currentUser = user;
  if (mergeGuest) {
    for (const meal of favorites) {
      try {
        await api("/api/favorites", { method: "POST", body: meal });
      } catch {
        /* skip anything the server rejects */
      }
    }
    localStorage.removeItem("recipeBoxFavorites");
  }
  try {
    const data = await api("/api/favorites");
    favorites = data.favorites;
  } catch {
    /* keep whatever we have */
  }
  renderAccountBar();
  refreshFavoriteUI();
}

async function logOut() {
  try {
    await api("/api/logout", { method: "POST", body: {} });
  } catch {
    /* ignore */
  }
  currentUser = null;
  favorites = loadFavorites(); // back to this browser's guest favorites
  renderAccountBar();
  refreshFavoriteUI();
}

accountBtn.addEventListener("click", () => {
  if (currentUser) logOut();
  else openAuthDialog("login");
});

function openAuthDialog(mode) {
  setAuthMode(mode);
  authForm.reset();
  authError.hidden = true;
  authDialog.hidden = false;
  authOverlay.hidden = false;
  authUsername.focus();
}
function closeAuthDialog() {
  authDialog.hidden = true;
  authOverlay.hidden = true;
}
function setAuthMode(mode) {
  authMode = mode;
  const isLogin = mode === "login";
  authTitle.textContent = isLogin ? "Log in" : "Create an account";
  authSubmit.textContent = isLogin ? "Log in" : "Sign up";
  authSwitchText.textContent = isLogin ? "New here?" : "Already have an account?";
  authSwitch.textContent = isLogin ? "Create an account" : "Log in";
  authPassword.autocomplete = isLogin ? "current-password" : "new-password";
}
authSwitch.addEventListener("click", () => setAuthMode(authMode === "login" ? "register" : "login"));
authClose.addEventListener("click", closeAuthDialog);
authOverlay.addEventListener("click", closeAuthDialog);

authForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  authError.hidden = true;
  authSubmit.disabled = true;
  try {
    const path = authMode === "login" ? "/api/login" : "/api/register";
    const { username } = await api(path, {
      method: "POST",
      body: { username: authUsername.value.trim(), password: authPassword.value },
    });
    closeAuthDialog();
    await onLoggedIn({ username });
  } catch (err) {
    authError.textContent = err.message;
    authError.hidden = false;
  } finally {
    authSubmit.disabled = false;
  }
});
