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
- Plugin URL: `https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/`
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
2. **Unit tests** — fuzzy match, aliases, command flow, sidebar cache, and pagination budget
3. **Build** — produces `dist/index.js` consumed by Revenge
4. **Manifest check** — validates `manifest.json`, confirms `dist/index.js` exists, and fails if the committed bundle is out of date

### Expected result

All steps exit with code 0. You should see:

```
Tests  86 passed (86)
dist/index.js  ~18kb
manifest ok (v4.5.2)
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
3. **New install:** tap **+**, paste `https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/`, confirm (allow unproxied if prompted).
4. **Update:** remove and re-add the plugin, or use Revenge's update/reload control if available.
5. **Reload Discord** fully (force-quit and reopen).
6. Confirm **Quick Server Switcher** appears in the plugin list and is enabled.

### Expected result

- Plugin loads without errors or crash on startup.
- Plugin settings screen opens when tapped.

---

## Part 3 — `/servers` command

**How to invoke options on mobile:** type `/`, tap **servers**, then fill the **query** and/or **page** fields in the slash UI and send. Typing plain text like `/servers something` is *not* a slash command — Discord will just post that string.


### 3.1 List servers (default)

**Steps**

1. In any channel, run `/servers` from the slash picker (do not send plain text).

**Expected**

- Prefer a **switcher sheet** (search box + tappable servers). If sheet APIs are missing, a **local bot-style reply** list appears instead.
- `/servers` appears **once** in slash suggestions (not duplicated).
- Sheet (or fallback list) shows your servers alphabetically; fallback header is `### Servers (N)`.
- Server names appear as bullet points (`•`).
- Names are sorted **alphabetically** (case-insensitive).
- Footer shows `Page 1 of X`.
- If you have 40 or fewer servers with short names, `X` is usually 1 and there is no "see more" hint.
- Very long server names may split earlier so each page stays under Discord's character limit.

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

## Part 4b — Recent servers

### 4b.1 Build history via plugin jumps

**Steps**

1. Run `/servers query:<known server>` for two different servers.
2. Run `/servers recent`.

**Expected**

- Numbered list of those servers (most recent first).
- Each line shows a `/servers rN` hint.
- History does **not** change when you switch servers only via Discord’s normal sidebar (low-risk mode).

### 4b.2 Jump via slot

**Steps**

1. From a populated recent list, run `/servers r1`.

**Expected**

- Navigates to that server + success toast.
- Running `/servers recent` again shows that server still (or again) at the top.

### 4b.3 Clear / size

**Steps**

1. In settings, tap **Clear recent**, then `/servers recent`.
2. Optionally change history size and confirm the stored count trims.

**Expected**

- Empty-history message after clear.
- Size field accepts 1–15.

---

## Part 4 — Fuzzy search and navigation

### 4.1 Prefix and subsequence match

**Steps**

1. Pick a server whose name you know, e.g. `Wayland High School`.
2. Run `/servers query:wsh` (or another subsequence of the name).

**Expected**

- Discord **navigates** to that server (guild switch): channel list / server header change to the target — not only a toast.
- Toast: `Jumped to <server name>` (success style).
- After the jump, `/servers recent` lists that server.

### 4.2 Exact and partial match priority

**Steps**

1. Run `/servers query:<exact server name>` for a known server.
2. Run `/servers query:<first few letters>` for a server whose name starts with those letters.

**Expected**

- Both resolve to the intended server when unambiguous.
- If multiple servers could match, the **first alphabetically** among the best match tier wins.
- Subsequence-only matches require at least **3** characters (e.g. `wsh` works; `ws` alone does not).
- If two or more servers share the best score, you get a **pick list** (no auto-jump) and a toast to refine the query.

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

## Part 5b — Excluded servers

### 5b.1 Exclude by name

**Steps**

1. Note two similarly named servers (or any server you can safely exclude).
2. In settings → **Excluded servers**, add the exact name of one server on its own line.
3. Run `/servers query:` with a term that previously matched the excluded server.

**Expected**

- Search no longer jumps to / lists that server as a match.
- Other servers still match normally.

### 5b.2 Partial exclude and list hide

**Steps**

1. Add a `~partial` rule (at least 2 characters) that matches an unwanted server.
2. Confirm search skips it.
3. Toggle **Hide excluded from /servers list** on, run `/servers`, then toggle off.

**Expected**

- With hide on, excluded names are absent from the list and the count drops.
- With hide off, excluded names still appear in the alphabetical list but are not searchable.

### 5b.3 Id exclude (optional)

**Steps**

1. With Developer Mode on, copy a server’s id and paste it as its own exclude line.
2. Search for that server’s name.

**Expected**

- No match / not jumped via search.

---

## Part 5 — Custom aliases

### 5.1 Configure aliases

**Steps**

1. Open plugin settings (**User Settings → Revenge → Plugins → Quick Server Switcher**).
2. In **Custom Aliases**, add a line: `short=Full Server Name`  
   Example: `chess=Maynard-area Chess Club`
3. Optionally add a target that itself contains `=` (only the first `=` is the separator).
4. Save implicitly (TextInput updates storage on change).

**Expected**

- Setting persists after leaving and re-opening settings.
- Alias targets may include `=` characters after the first separator.

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

### 5.4 Export / import aliases

**Steps**

1. With at least one valid alias configured, tap **Copy**.
2. Clear the alias field (or edit it), then tap **Import**.

**Expected**

- Copy toast reports how many aliases were copied.
- Import merges clipboard lines; duplicate alias keys prefer the imported target.
- Malformed clipboard lines are skipped and mentioned in the toast when relevant.

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
- Re-open the guild drawer after toggling if the list does not refresh immediately.
- If Flat Sidebar is on but the client cannot patch the guild list, a danger toast explains it is unavailable.

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
| Version | Check plugin metadata if Revenge shows it | **4.5.2** |
| Ambiguous search | Two servers sharing a prefix, query that prefix | Pick list + refine toast; no jump |
| Excluded search | Exclude one of two similar names, query shared fragment | Only non-excluded server matches |
| Debug logging | Enable in settings, run `/servers` / toggle flat sidebar | No crash; diagnostics appear in Revenge logs when supported |

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

## Quick checklist — v4.5.2 device QA (A1)

Copy this for the release candidate. Prefer a fresh plugin install/update from the **raw** GitHub URL, then full Discord reload.

**Already confirmed on device (do not skip re-check after `main` install):** enable works, settings open, `/servers` appears once, list posts as a local bot reply.

**Still needs human testing (priority):** actually **moving** to another server via search / recent / alias — toast alone is not enough; confirm the guild UI switches.

```
[ ] make verify — all green locally (or CI green on main)
[ ] Plugin installs / updates on Revenge without crash (shows 4.5.2 if version visible)
  Install URL: https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/
[ ] Smoke plugin installs and ENABLES (toggle on, no X)
  Smoke URL: https://raw.githubusercontent.com/djbclark/RevengeQuickSwitcher/main/smoke/
[ ] Main plugin installs and ENABLES after smoke passes
[ ] Settings open; readable in light and dark theme
[ ] /servers — opens top switcher; Close dismisses; tap jumps and closes overlay
[ ] Settings → Copy debug logs — pastes recent switcher/nav lines
[ ] Settings → Open switcher — same sheet without slash
[ ] /servers page:2 — pagination still posts in-channel (if 41+ servers or very long names)
[ ] Ambiguous query — tappable pick sheet (C5); markdown fallback if needed
[ ] NAV: /servers query:<unique fuzzy> — Discord switches to that server (sidebar/header change), success toast
[ ] NAV: stay on a different server first, then jump — confirm you leave the old guild, not just toast
[ ] NAV: /servers recent after a plugin jump — list shows it; /servers r1 jumps back (UI switches)
[ ] Sidebar-only guild tap does NOT add to recent (only plugin jumps count)
[ ] /servers query:<shared-prefix> — pick list in-channel, no jump
[ ] /servers query:<unknown> — "No match found"; stay on current server
[ ] Exclude exact name — search skips that server
[ ] Exclude ~partial — search skips matching names
[ ] Hide excluded from list — on hides / off shows in /servers
[ ] Custom alias — settings + NAV jump to target server
[ ] Alias Copy / Import — clipboard round-trip works
[ ] Flat sidebar — on flattens/sorts, off restores folders
[ ] Debug logging toggle — no crash
[ ] Reload Discord — still works after restart
```

When finished, note pass/fail in a GitHub issue or reply in chat so **A1** can be marked done in `OPTIONS.md`.

---

## Legacy quick checklist (superseded by v4.4.0 block above)

```
[ ] make verify — all green locally
[ ] Plugin installs / updates on Revenge without crash
[ ] /servers — alphabetical list as local bot reply, correct count; command appears once
[ ] /servers 2 — pagination (if 41+ servers)
[ ] /servers recent + r1 — history from plugin jumps only
[ ] /servers query:<fuzzy> — jumps to server + success toast
[ ] /servers query:<shared-prefix> — pick list, no jump
[ ] /servers query:<unknown> — "No match found"
[ ] Custom alias — settings + jump works
[ ] Alias Copy / Import — clipboard round-trip works
[ ] Flat sidebar — on flattens/sorts, off restores folders
[ ] Debug logging toggle — no crash
[ ] Settings readable in light and dark theme
[ ] Reload Discord — still works after restart
```
