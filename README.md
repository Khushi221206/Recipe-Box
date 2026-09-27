# The Recipe Box 🍲

A lightweight, distraction-free recipe finder web app. Search for recipes by dish name or by a single ingredient you already have at home, view full ingredients and method, and save favorites — all with no sign-up, no backend, and no database.

**Live demo:** [Add your deployed GitHub Pages link here]

## Features

- 🔍 Search by dish name **or** by ingredient
- 📋 Full recipe detail — ingredients with quantities, and step-by-step method
- ❤️ Save recipes to Favorites, persisted locally via `localStorage` (no account needed)
- 🎲 "Surprise me" — get a random recipe
- 🗂️ Filter results by category, sort A–Z / Z–A
- 📱 Fully responsive — works on mobile, tablet, and desktop

## Tech Stack

- **HTML5** — semantic page structure
- **CSS3** — custom design system (CSS variables, Grid, Flexbox, animations)
- **JavaScript (ES6+)** — vanilla JS, no frameworks; Fetch API + async/await
- **[TheMealDB](https://www.themealdb.com/api.php)** — free public recipe API
- **Browser `localStorage`** — favorites persistence

No build tools, no dependencies to install — just static files.

## Project Structure

```
recipe-box/
├── index.html   → page structure
├── style.css    → design system & layout
├── script.js    → search, rendering, favorites, modal logic
└── README.md
```

## Running Locally

1. Clone or download this repository.
2. Open `index.html` directly in any modern browser — no server or build step required.
3. Make sure you're connected to the internet (recipe data is fetched live from TheMealDB).

## Deployment

This app is a fully static site and can be hosted anywhere — GitHub Pages, Netlify, Vercel, or any static file host. See the project report's Deployment chapter for step-by-step GitHub Pages instructions.

## Credits

- Recipe data courtesy of [TheMealDB](https://www.themealdb.com/)
- Fonts via [Google Fonts](https://fonts.google.com/) — Fraunces, Work Sans, IBM Plex Mono

## License

Built as a student mini-project. Free to use and adapt for learning purposes.
