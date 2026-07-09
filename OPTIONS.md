# Options — RevengeQuickSwitcher

Living backlog of product and engineering options. Keep this file current whenever priorities change, and push updates to GitHub with the related work.

**How to reference:** each section has a letter; each option has a number. Say **A1**, **C3**, etc.

Status legend: **Ready** · **Needs input** · **Done** · **Idea**

---

## A — Needs human input

| ID | Option | Why blocked | Notes |
|----|--------|-------------|-------|
| **A1** | Device QA | Requires a Revenge Discord client and manual checklist | Walk `TESTING.md` after each release candidate. |

---

## B — Recently shipped

| ID | Option | Status | Summary |
|----|--------|--------|---------|
| **B1** | Manifest author Discord ID | **Done** | `authors[].id` set to `689173209785958424`. |
| **B2** | Search pick-list on ties | **Done** (v4.1.0) | List tied matches instead of auto-jumping. |
| **B3** | Theme-aware settings | **Done** (v4.1.0) | Semantic tokens with dark fallbacks. |
| **B4** | Debug logging toggle | **Done** (v4.1.0) | Metro/patch/command diagnostics. |
| **B5** | Versioned release | **Done** (v4.1.0) | GitHub tag + release notes. |
| **B6** | Changelog + semver policy | **Done** | Documented in `CHANGELOG.md`. |
| **B7** | Export / import aliases | **Done** (v4.2.0) | Copy aliases to clipboard; import/merge from clipboard. |

---

## C — Feature ideas

### C1 — Recent-servers jump

**Problem:** Fuzzy search is great when you know a name fragment; switching among a handful of frequent servers is still slower than it could be.

**Idea:** Track the last N guilds visited (via navigation hooks or guild-select patches). Expose:

- `/servers recent` — list recent servers
- `/servers query:r1` / numeric shortcodes — jump to recent slot
- Optional settings: history size (e.g. 5–15), clear history

**Complexity:** Medium · **Risk:** Metro churn on guild-select · **Fit:** High

### C2 — Channel search / jump

**Problem:** Users often want a specific channel, not just the server.

**Idea:** Extend `/servers` or add `/channels` with channel-name search (current guild or cross-guild), `guild:channel` syntax, and Metro navigation.

**Complexity:** High · **Risk:** Large Metro surface · **Fit:** Strong (maybe separate plugin)

### C3 — Folder-aware (non-flat) sort

**Problem:** Flat sidebar destroys intentional folder grouping.

**Idea:** Modes: `off` | `flat` | `sort-within-folders` | `sort-folders`.

**Complexity:** Medium · **Risk:** Folder node shape variance · **Fit:** Natural Flat Sidebar extension

### C4 — Favorites / pinned servers

**Problem:** Aliases help search, but don’t change list or sidebar priority.

**Idea:** Pin guild IDs; show first in `/servers` and optionally at top of flat sidebar.

**Complexity:** Low–medium · **Risk:** Low · **Fit:** Complements aliases / recent

### C5 — Interactive disambiguation UI

**Problem:** Pick-lists in command replies aren’t tappable.

**Idea:** When multiple servers tie, open a Revenge/Vendetta confirmation alert or action sheet listing matches. Tapping one jumps immediately. If alert modules aren’t available, keep today’s markdown pick-list fallback.

**Why it matters:** Command responses are read-only text. On mobile, refining a query is slower than tapping the intended server. An interactive sheet closes that gap without teaching users a new command.

**Likely approach:**

1. Detect tie in `executeServersCommand` (already done).
2. Call a UI dep such as `showPicker(matches)` from the plugin layer.
3. Try Metro/Revenge alert APIs (`showConfirmationAlert`, custom alert, action sheet).
4. On failure or missing module, return the existing pick-list content.

**Complexity:** Medium · **Risk:** Alert APIs differ across Revenge builds · **Fit:** Direct upgrade to B2

### C6 — Export / import aliases

**Status:** **Done** (v4.2.0) — see B7.

### C7 — Mute / exclude servers from search

**Problem:** Noisy or similarly named servers steal fuzzy matches.

**Idea:** Per-guild exclude list ignored by search and optionally hidden from `/servers`.

**Complexity:** Low–medium · **Risk:** Low · **Fit:** Pairs with pick-list and favorites

---

## D — Engineering / maintenance

| ID | Option | Status | Notes |
|----|--------|--------|-------|
| **D1** | Integration smoke test harness | **Idea** | Document expected Metro props; optional runtime self-check when debug logging is on. |
| **D2** | Changelog discipline | **Done** | Keep `CHANGELOG.md` in sync with tags/releases (see policy in that file). |
| **D3** | Semantic versioning policy | **Done** | Patch / minor / major rules live at the top of `CHANGELOG.md`. |

---

## How to maintain this file

1. Assign every option a stable **letter+number** ID; do not renumber shipped IDs—mark them **Done** instead.
2. When finishing work, update status tables and push with the related commit.
3. Prefer short tables plus a fleshed-out subsection for non-trivial ideas.
