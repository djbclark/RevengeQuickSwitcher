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
| **A1** | Device QA | **Low** (process) | Requires a Revenge Discord client and manual checklist | Install **smoke/** first, then main plugin from raw URLs. Walk **v4.4.6** checklist in `TESTING.md`. |

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
| **B8** | Recent-servers jump (low-risk) | **Done** (v4.3.0) | **Low** | History only when this plugin navigates; no guild-select hooks. |
| **B9** | Mute / exclude servers | **Done** (v4.4.0) | **Low** | Name/id/`~partial` rules; optional hide from list. |
| **B10** | Fix Revenge install URL / polymanifest | **Done** (v4.4.1) | **Low** | Raw GitHub URL + Vendetta-compatible bundle/`hash`. |
| **B11** | Fix plugin enable / settings wrench | **Done** (v4.4.2) | **Low** | Command description + resilient onLoad/settings. |
| **B12** | Vendetta IIFE rebuild + smoke plugin | **Done** (v4.4.3) | **Low** | Match known-working bundle shape; isolate load failures. |
| **B13** | Main enable after smoke OK | **Done** (v4.4.4) | **Low** | ES2015 Hermes-safe bundle + no eval-time storage/`this`. |
| **B14** | `/servers` missing from slash menu | **Done** (v4.4.5) | **Low** | Revenge inverted `shouldHide` filter; omit it + fill command metadata. |
| **B15** | `/servers` silent + duplicate | **Done** (v4.4.6) | **Low** | `sendBotMessage` replies; unregister-before-register. |

---

## C — Feature ideas

### C1 — Recent-servers jump

**Status:** **Done** (v4.3.0, low-risk path) — see B8.

**Shipped:** `/servers recent`, `/servers rN`, history size + clear in settings. History updates only when Quick Server Switcher successfully jumps.

**Possible follow-up (not scheduled):** auto-track via guild-select Metro hooks.

**Risk (follow-up):** **Medium–High** — Discord “current guild” / select modules churn.  
**Risk (shipped path):** **Low**

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

**Status:** **Done** (v4.4.0) — see B9.

**Shipped:** Settings text rules (exact name, Discord id, or `~partial`); always skipped by fuzzy search; optional hide from `/servers` list. Recents slots still work for previously recorded ids.

**Risk:** **Low**
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
