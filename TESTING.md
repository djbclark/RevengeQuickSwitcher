# Testing RevengeQuickSwitcher

This guide covers verification before a release: automated checks on your machine, then manual validation on a Revenge Discord client.

## Prerequisites

### Local (developer machine)

- Node.js 18+ (20+ recommended)
- npm
- Repository cloned and dependencies installed:

```bash
git clone https://github.com/djbclark/RevengeQuickSwitcher.git
cd RevengeQuickSwitcher
make install
```

### Device (Revenge client)

- Discord mobile with **Revenge** installed and working
- Plugin URL: `https://github.com/djbclark/RevengeQuickSwitcher`
- At least **2 servers** joined (more is better for pagination and search tests)
- Optional: **40+ servers** to exercise pagination fully
- Optional: at least one **server folder** in the sidebar for flat-sidebar tests

---

## Part 1 — Local automated verification

Run the full pipeline before every release or device test session:

```bash
make verify
```

This runs, in order:

1. **Typecheck** — `command.ts`, `sidebar.ts`, `utils.ts`, and `index.tsx`
2. **Unit tests** — 48 tests across fuzzy match, aliases, command flow, and sidebar logic
3. **Build** — produces `dist/index.js` consumed by Revenge
4. **Manifest check** — validates `manifest.json` and confirms `dist/index.js` exists

### Expected result

All steps exit with code 0. You should see:

```
Tests  48 passed (48)
dist/index.js  ~4–5kb
manifest ok (v4.0.0)
```

### Individual commands

| Command | Purpose |
|---------|---------|
| `make test` | Run tests only |
| `make typecheck` | Type-check all `src/` modules |
| `make build` | Rebuild `dist/index.js` after source edits |
| `make verify` | Full pre-release pipeline (same as CI) |

If local verification fails, fix the issue before testing on device.

---

## Part 2 — Install or update on Revenge

1. Open Discord on your device.
2. Go to **User Settings → Revenge → Plugins**.
3. **New install:** tap **+**, paste `https://github.com/djbclark/RevengeQuickSwitcher`, confirm.
4. **Update:** remove and re-add the plugin, or use Revenge's update/reload control if available.
5. **Reload Discord** fully (force-quit and reopen).
6. Confirm **Quick Server Switcher** appears in the plugin list and is enabled.

### Expected result

- Plugin loads without errors or crash on startup.
- Plugin settings screen opens when tapped.

---

## Part 3 — `/servers` command

### 3.1 List servers (default)

**Steps**

1. In any channel, run `/servers`.

**Expected**

- Response shows a markdown list headed `### Servers (N)` where N is your server count.
- Server names appear as bullet points (`•`).
- Names are sorted **alphabetically** (case-insensitive).
- Footer shows `Page 1 of X`.
- If you have 40 or fewer servers, `X` is 1 and there is no "see more" hint.

### 3.2 Pagination

**Steps**

1. If you have **41+ servers**, run `/servers` and note the footer.
2. Run `/servers 2` (page option or numeric query).
3. If more pages exist, try the next page number from the footer hint.

**Expected**

- Page 2 shows different servers than page 1.
- Footer updates to `Page 2 of X`.
- When on the last page, footer may say `Use /servers 1 to return to the start.`
- When not on the last page, footer includes `Use /servers N to see more.`
- Page numbers beyond the last page clamp to the final page (no crash, no empty list).

### 3.3 Numeric query as page alias

**Steps**

1. Run `/servers` with the **query** field set to a number only, e.g. `2` (same as `/servers page:2`).

**Expected**

- Behaves like pagination, not a server name search.

---

## Part 4 — Fuzzy search and navigation

### 4.1 Prefix and subsequence match

**Steps**

1. Pick a server whose name you know, e.g. `Wayland High School`.
2. Run `/servers query:wsh` (or another subsequence of the name).

**Expected**

- Discord navigates to that server (guild switch).
- Toast: `Jumped to <server name>` (success style).

### 4.2 Exact and partial match priority

**Steps**

1. Run `/servers query:<exact server name>` for a known server.
2. Run `/servers query:<first few letters>` for a server whose name starts with those letters.

**Expected**

- Both resolve to the intended server when unambiguous.
- If multiple servers could match, the **first alphabetically** among the best match tier wins.

### 4.3 No match

**Steps**

1. Run `/servers query:zzzznotaserver`.

**Expected**

- Toast: `No match found` (danger/error style).
- You stay on the current server.

### 4.4 Whitespace-only query

**Steps**

1. Run `/servers query:` with an empty or spaces-only value (if the client allows it).

**Expected**

- Falls back to **list mode** (same as `/servers`), not search mode.

---

## Part 5 — Custom aliases

### 5.1 Configure aliases

**Steps**

1. Open plugin settings (**User Settings → Revenge → Plugins → Quick Server Switcher**).
2. In **Custom Aliases**, add a line: `short=Full Server Name`  
   Example: `chess=Maynard-area Chess Club`
3. Save implicitly (TextInput updates storage on change).

**Expected**

- Setting persists after leaving and re-opening settings.

### 5.2 Jump via alias

**Steps**

1. Run `/servers query:short` using the alias from 5.1.

**Expected**

- Resolves to the target server name and navigates there.
- Success toast shows the **sanitized server name**, not the alias string.

### 5.3 Invalid alias lines

**Steps**

1. Add malformed lines (`noequals`, `=targetonly`, `alias=`) alongside one valid line.
2. Run `/servers query:<valid alias>`.

**Expected**

- Valid aliases still work; malformed lines are ignored.

---

## Part 6 — Flat sidebar

### 6.1 Enable flat sidebar

**Steps**

1. In plugin settings, enable **Flat Sidebar**.
2. Open the server list sidebar (guild drawer).

**Expected**

- Toast confirms: `Sidebar set to Flat`.
- Folders are **flattened** — all servers appear in one list.
- Servers are sorted **A–Z** by name.
- Order persists while scrolling and after switching channels.

### 6.2 Disable flat sidebar

**Steps**

1. Disable **Flat Sidebar** in settings.
2. Re-open the guild drawer.

**Expected**

- Toast: `Sidebar set to Standard`.
- Discord's native folder layout returns.

### 6.3 Cache behavior (informal)

**Steps**

1. With flat sidebar on, note the order.
2. Switch servers a few times without changing folder membership.

**Expected**

- Order stays stable; no flicker or reorder on every navigation.

---

## Part 7 — Edge cases and regression checks

| Scenario | Steps | Expected |
|----------|-------|----------|
| No servers | Use a test account with zero guilds (if available) | Toast: `No servers found` |
| Unresolvable guild id | Rare — match found but guild object has no id | Toast: `Could not resolve server id` |
| Markdown in names | Server name with `_` or `*` | Listed names escaped in `/servers` output (no broken markdown) |
| Long server names | Name > 100 chars | Truncated safely in lists and toasts |
| Plugin reload | Disable plugin, re-enable, reload Discord | `/servers` and settings still work |
| Version | Check plugin metadata if Revenge shows it | **4.0.0** |

---

## Part 8 — Reporting issues

If something fails, open a [GitHub Issue](https://github.com/djbclark/RevengeQuickSwitcher/issues/new) with:

1. **Revenge / Discord version** (if known)
2. **Plugin version** (from `manifest.json` or release tag)
3. **Exact command or setting** used
4. **Expected vs actual** behavior
5. **Screenshots or toasts** if possible
6. Whether `make verify` passed locally

For device-only bugs, note that local tests passed — that helps separate Revenge integration issues from logic bugs.

---

## Quick checklist (copy for releases)

```
[ ] make verify — all green locally
[ ] Plugin installs / updates on Revenge without crash
[ ] /servers — alphabetical list, correct count
[ ] /servers 2 — pagination (if 41+ servers)
[ ] /servers query:<fuzzy> — jumps to server + success toast
[ ] /servers query:<unknown> — "No match found"
[ ] Custom alias — settings + jump works
[ ] Flat sidebar — on flattens/sorts, off restores folders
[ ] Reload Discord — still works after restart
```
