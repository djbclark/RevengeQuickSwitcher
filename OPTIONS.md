# Options — RevengeQuickSwitcher

Living backlog of product and engineering options. Keep this file current whenever priorities change, and push updates to GitHub with the related work.

Status legend: **Ready** (can implement now) · **Needs input** (blocked on a human decision) · **Done** (shipped; keep briefly for history) · **Idea** (not scheduled)

---

## Needs human input

| Option | Why blocked | Notes |
|--------|-------------|-------|
| **Device QA** | Requires a Revenge Discord client and manual checklist | Walk `TESTING.md` after each release candidate. |

---

## Ready / recently shipped

| Option | Status | Summary |
|--------|--------|---------|
| Manifest author Discord ID | **Done** | `authors[].id` set to `689173209785958424` in `manifest.json`. |
| Search pick-list on ties | **Done** (v4.1.0) | When several servers share the best match score, list them instead of auto-jumping. |
| Theme-aware settings | **Done** (v4.1.0) | Settings colors resolve from Discord semantic tokens with dark fallbacks. |
| Debug logging toggle | **Done** (v4.1.0) | Plugin setting that logs Metro/patch/command diagnostics via Revenge logger. |
| Versioned release | **Done** (v4.1.0) | Tagged GitHub release after the above. |

---

## Something new (feature ideas)

### 1. Recent-servers jump

**Problem:** Fuzzy search is great when you know a name fragment; switching among a handful of frequent servers is still slower than it could be.

**Idea:** Track the last N guilds visited (via navigation hooks or guild-select patches). Expose:

- `/servers recent` — list recent servers
- `/servers query:r1` / numeric shortcodes — jump to recent slot
- Optional settings: history size (e.g. 5–15), clear history

**Complexity:** Medium (storage + patch or poll for current guild).  
**Risk:** Discord API churn on guild-select modules.  
**Fit:** High — aligns with “quick switcher” positioning.

### 2. Channel search / jump

**Problem:** Users often want a specific channel, not just the server.

**Idea:** Extend `/servers` or add `/channels`:

- Search channel names within the current guild, or across guilds
- Jump via existing navigation (`transitionToChannel` / similar Metro APIs)
- Optional: `guild:channel` query syntax

**Complexity:** High (channel stores, permissions, large result sets, pagination).  
**Risk:** Heavier Metro surface; easier to break on Discord updates.  
**Fit:** Strong power-user feature; may deserve a separate plugin if scope grows.

### 3. Folder-aware (non-flat) sort

**Problem:** Flat sidebar destroys intentional folder grouping. Some users want A–Z **inside** folders, or folders sorted by name while keeping membership.

**Idea:** Setting with modes:

- `off` — Discord default
- `flat` — current behavior
- `sort-within-folders` — keep folders, sort guilds inside each
- `sort-folders` — sort folder nodes by folder name, preserve children order or also sort children

**Complexity:** Medium (extend `sidebar.ts` transforms; more cache fingerprints).  
**Risk:** Folder node shapes vary; need defensive parsing + device tests.  
**Fit:** Natural extension of Flat Sidebar.

### 4. Favorites / pinned servers

**Problem:** Aliases help search, but don’t change list or sidebar priority.

**Idea:** Pin a set of guild IDs in settings; show them first in `/servers` list and optionally pin them to the top of the flat sidebar.

**Complexity:** Low–medium.  
**Risk:** Low.  
**Fit:** Complements aliases and recent history.

### 5. Disambiguation UI beyond command replies

**Problem:** Pick-lists in command responses work, but aren’t interactive.

**Idea:** Use Revenge/Vendetta alerts or a custom action sheet to tap a match (when multiple ties). Fall back to markdown list when alerts aren’t available.

**Complexity:** Medium (UI module discovery + fallbacks).  
**Risk:** Alert APIs differ across Revenge builds.  
**Fit:** Improves the tie pick-list shipped in v4.1.0.

### 6. Export / import aliases

**Problem:** Reinstalling or switching devices loses alias text.

**Idea:** Settings actions to copy aliases to clipboard and paste/import a block. Optional share as a gist URL later.

**Complexity:** Low.  
**Risk:** Low (clipboard module availability).  
**Fit:** Quality-of-life for power users with long alias lists.

### 7. Mute / exclude servers from search

**Problem:** Noisy or similarly named servers steal fuzzy matches.

**Idea:** Per-guild exclude list (by id or name pattern) ignored by search and optionally hidden from `/servers` listing.

**Complexity:** Low–medium.  
**Risk:** Low.  
**Fit:** Pairs well with pick-list and favorites.

---

## Engineering / maintenance ideas

| Idea | Notes |
|------|--------|
| Integration smoke test harness | Document Metro props expected (`getSortedGuilds`, `transitionToGuild`); optional runtime self-check command when debug logging is on. |
| Changelog file | Keep `CHANGELOG.md` in sync with GitHub releases. |
| Semantic versioning policy | Patch = fixes; minor = user-visible features; major = breaking command/settings changes. |

---

## How to maintain this file

1. When finishing a chunk of work, move items between **Needs input**, **Ready**, **Done**, and **Something new**.
2. Prefer short status tables plus a fleshed-out section for non-trivial ideas.
3. Commit and push `OPTIONS.md` whenever it changes (alone or with related code).
