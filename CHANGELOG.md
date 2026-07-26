# Changelog

## 1.2.0 — 2026-07-26

- Renamed to **Bury Explain** (was "Bury & Explain") across all user-visible
  surfaces; package/module names unchanged
- Sidebar reliability: the whole trigger path is now observable — any failure
  surfaces as a tooltip and a stderr message and still falls back to opening
  the AI in your system browser, so help always reaches you
- The web profile is now kept alive without a parent widget so it can't be
  torn down before its pages
- New top-toolbar plain-text **"AI"** button that toggles the sidebar at your
  provider's home page (no card failure required)
- Distinct text-only sidebar chrome: an "AI · <Provider>" header with flat
  "↗ browser" and "✕" buttons — no icons, logos, or images
- New **`add_tag`** option (and a "Tag the card" checkbox) to bury without
  tagging

- Default prompt now audits the failed card against Piotr Wozniak's "Twenty
  rules of formulating knowledge" and suggests concrete rewrites for any
  rule it violates, in addition to the existing simple explanation,
  mnemonic, and likely-confusion help

## 1.0.0 — 2026-07-26

- Initial release
- Auto-bury cards that fail past a configurable threshold within a rolling time window
- Instant AI explanation with the failing card pre-searched, across 6 providers (including a custom URL)
- Sidebar view with persistent login
- Minimalist single-dialog options screen
- Offline-safe: reviewing continues normally if the AI provider is unreachable
