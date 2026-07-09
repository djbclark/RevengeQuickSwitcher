# Options — RevengeQuickSwitcher

Living backlog of product and engineering options. Keep this file current whenever priorities change, and push updates to GitHub with the related work.

**How to reference:** each section has a letter; each option has a number. Say **A1**, **C3**, etc.

Status legend: **Ready** · **Needs input** · **Done** · **Idea**

**Risk scale:** **Low** (mostly our code / storage) · **Medium** (some Metro/UI discovery; graceful fallbacks possible) · **High** (deep Discord internals; easy to break on client updates)

Every option below must include an explicit **Risk** value.

---

## A — Needs human input

| ID | Option | Risk | Why blocked | Notes |
|----|--------|------|-------------|-------|
| **A1** | Device QA | **Low** (process) | Requires a Revenge Discord client and manual checklist | Walk `TESTING.md` after each release candidate. Missed regressions are the real product risk if skipped. |

---

## B — Recently shipped

| ID | Option | Status | Risk | Summary |
|----|--------|--------|------|---------|
| **B1** | Manifest author Discord ID | **Done** | **Low** | `authors[].id` set to `689173209785958424`. |
| **B2** | Search pick-list on ties | **Done** (v4.1.0) | **Low** | List tied matches instead of auto-jumping. |
| **B3** | Theme-aware settings | **Done** (v4.1.0) | **Medium** | Semantic tokens with dark fallbacks. |
| **B4** | Debug logging toggle | **Done** (v4.1.0) | **Low** | Metro/patch/command diagnostics. |
| **B5** | Versioned release | **Done** (v4.1.0) | **Low** | GitHub tag + release notes. |
| **B6** | Changelog + semver policy | **Done** | **Low** | Documented in `CHANGELOG.md`. |
| **B7** | Export / import aliases | **Done** (v4.2.0) | **Medium** | Clipboard APIs vary; toast if unavailable. |

---

## C — Feature ideas

### C1 — Recent-servers jump

**What it is:** Remember the last N servers you actually opened, then jump back to them quickly without retyping a fuzzy query.

**User-facing shape:**

- `/servers recent` — numbered list of recent guilds
- `/servers query:r1` (or `r2`…) — jump to that recent slot
- Settings: history size (e.g. 5–15), clear history

**How it would work:** Persist an ordered list of guild IDs in plugin storage. Append/update whenever the user navigates to a guild (patch guild-select / `transitionToGuild`, or poll the selected-guild store). Deduplicate and cap length.

**Why bother:** Fuzzy search helps when you remember a name fragment. Recent history helps when you bounce between the same few servers all day—closer to a true “quick switcher.”

**Complexity:** Medium  
**Risk:** **Medium–High** for automatic tracking (depends on Discord Metro modules for “current guild” / select hooks; those churn). **Low** if v1 is manual-only (“mark current as recent” / record only when `/servers` successfully jumps). Prefer starting with the low-risk path, then add auto-track behind debug logging.  
**Fit:** High — core to the product name/positioning  
**Depends on / pairs with:** C4 (pins stay sticky; recents stay temporal), C5 (if recent list is shown as a picker)

### C2 — Channel search / jump

**What it is:** Search and jump to channels, not only servers.

**Complexity:** High  
**Risk:** **High** — channel stores, permissions, and navigation APIs are a large Metro surface and break often across Discord versions.  
**Fit:** Strong power-user feature; may deserve a separate plugin

### C3 — Folder-aware (non-flat) sort

**What it is:** Keep Discord folders, but sort inside them and/or sort folder nodes—modes beyond today’s all-or-nothing flat list.

**Complexity:** Medium  
**Risk:** **Medium** — folder node shapes vary; need defensive parsing and device tests. Wrong assumptions can scramble the sidebar.  
**Fit:** Natural Flat Sidebar extension

### C4 — Favorites / pinned servers

**What it is:** A user-chosen set of servers that always float to the top of `/servers` (and optionally the flat sidebar), independent of alphabetical order or recent activity.

**User-facing shape:**

- Settings: list or multi-select of pinned guilds (by name/id), reorder, clear
- `/servers` list: pinned block first, then the rest A–Z (or under a “Pinned” heading)
- Optional: flat sidebar pins the same IDs to the top
- Optional later: `/servers query:p1` shortcodes like recents

**How it would work:** Store ordered guild IDs in plugin storage. When building the sorted guild list for the command (and optionally `transformFlatSidebar`), partition into pinned vs unpinned, preserve pin order, sort the remainder as today. Resolve names via GuildStore; drop or flag stale IDs if a server was left.

**Why bother:** Aliases speed *search*. Pins change *priority and visibility*. A school server you always want first shouldn’t depend on remembering `wsh` or hoping it was recent.

**Vs C1:** Pins are explicit and stable; recents are automatic and change as you navigate. Many switchers offer both.

**Complexity:** Low–medium (command list is straightforward; sidebar pinning needs care with folders when flat mode is off)  
**Risk:** **Low** for `/servers` list-only pins (pure data + existing sort pipeline). **Medium** if also rewriting flat-sidebar order (same patch path as today; must not break folder mode / cache checksums). Stale IDs after leaving a server are a mild UX risk, not a crash risk if handled.  
**Fit:** High QoL; complements aliases and C1  
**Depends on / pairs with:** C1, C7 (exclude), B7 (could export pins later)

### C5 — Interactive disambiguation UI

**What it is:** Tappable alert/action sheet when multiple servers tie, instead of a read-only markdown pick list.

**Complexity:** Medium  
**Risk:** **Medium** — Revenge/Vendetta alert APIs differ by build; must keep markdown fallback (B2).  
**Fit:** Direct upgrade to B2

### C6 — Export / import aliases

**Status:** **Done** (v4.2.0) — see B7.  
**Risk:** **Medium** (clipboard module availability) — mitigated with toasts when unavailable.

### C7 — Mute / exclude servers from search

**What it is:** Hide noisy or similarly named servers from fuzzy search and optionally from `/servers` listing.

**Complexity:** Low–medium  
**Risk:** **Low** — storage + filter in existing pure command path; little Metro exposure.  
**Fit:** Pairs with pick-list and favorites

---

## D — Engineering / maintenance

| ID | Option | Status | Risk | Notes |
|----|--------|--------|------|-------|
| **D1** | Integration smoke test harness | **Idea** | **Low** | Document expected Metro props; optional runtime self-check when debug logging is on. Worst case: noisy logs, not broken navigation. |
| **D2** | Changelog discipline | **Done** | **Low** | Keep `CHANGELOG.md` in sync with tags/releases. |
| **D3** | Semantic versioning policy | **Done** | **Low** | Patch / minor / major rules live at the top of `CHANGELOG.md`. |

---

## How to maintain this file

1. Assign every option a stable **letter+number** ID; do not renumber shipped IDs—mark them **Done** instead.
2. Always include **Risk** (Low / Medium / High, with a short reason).
3. When finishing work, update status tables and push with the related commit.
4. Prefer short tables plus a fleshed-out subsection for non-trivial ideas.
