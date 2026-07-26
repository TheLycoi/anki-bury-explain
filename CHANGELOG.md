# Changelog

## 1.1.0 — 2026-07-26

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
