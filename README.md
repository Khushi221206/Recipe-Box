# The Recipe Box 🍲
A mini project — Recipe Finder built with plain **HTML, CSS, and JavaScript**.

## What it does
- Search recipes **by dish name** or **by ingredient**
- "Surprise me" button pulls a random recipe
- Click any recipe card to open full details: ingredients, quantities, and step-by-step method
- Filter results by category and sort A–Z / Z–A
- Save recipes to a **Favorites drawer** (persisted with `localStorage`, so it survives a page refresh)
- Loading skeletons, empty-state, and error handling
- Fully responsive, keyboard-accessible (focus rings, Escape to close modals)

## Tech
- **HTML5** — semantic structure (`index.html`)
- **CSS3** — custom design system with CSS variables, grid layout, animations (`style.css`)
- **Vanilla JavaScript (ES6+)** — `fetch`, async/await, DOM manipulation, `localStorage` (`script.js`)
- **API**: [TheMealDB](https://www.themealdb.com/api.php) — free public API, no key/signup required (uses the shared test key `1`)

## How to run
No build step needed.
1. Download all files (`index.html`, `style.css`, `script.js`) into the same folder.
2. Open `index.html` in any browser (or right-click → "Open with Live Server" in VS Code).
3. You need an internet connection, since recipe data is fetched live from TheMealDB.

## Project structure
```
recipe-finder/
├── index.html   # markup
├── style.css    # styling (vintage recipe-card theme)
├── script.js    # search, favorites, modal logic
└── README.md
```

## Ideas to extend it
- Add a "shopping list" that collects ingredients across saved recipes
- Cache API responses in `localStorage` to reduce repeat network calls
- Add pagination or infinite scroll for large result sets
- Swap in a different recipe API and compare data shapes
