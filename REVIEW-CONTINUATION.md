# Code review continuation prompt (2026-07-19 session)

> **If resuming after an out-of-tokens cutoff, paste this to the new session:**
>
> "Continue the code review + fixup of RevengeQuickSwitcher described in
> REVIEW-CONTINUATION.md. Read that file first, pick up at the first unchecked
> item under 'Review plan', keep this file updated as you go, and commit a
> checkpoint after each batch of fixes. Focus on the non-QA plugin code
> (src/*.ts, src/*.tsx); ignore scripts/ device-QA automation (build.mjs /
> check-manifest.mjs ARE in scope). Verify with `npm run verify` before each
> commit."

## Ground rules established this session

- Scope: plugin source (`src/*.ts`, `src/*.tsx`) + build/manifest scripts.
  OUT of scope: `scripts/` device-QA harness (device_qa_qss.py etc.), VLM/OCR tooling.
- Checkpoints = git commits on `main` after each verified batch of fixes.
- HANDOFF.md has uncommitted edits ( M ) predating this session — deliberately
  left out of review commits.
- Version bumped 4.5.9 → 4.5.10 (repo policy: shipped dist changes bump patch;
  debug ring keys off version).

## Review plan / progress

- [x] **Checkpoint 1 (commit 82355bd) — repo hygiene:** stray `tsc` emit
  (`src/*.js`) shadowed sources and broke 2 test files. Deleted, gitignored
  `src/*.js`, `noEmit: true` in tsconfig.json. 96 tests green.
- [x] Review `src/utils.ts` — clean; added `truncateForDisplay`, clamped pick-list header.
- [x] Review `src/aliases.ts`, `src/excludes.ts`, `src/recents.ts` — clean, no changes.
- [x] Review `src/command.ts` — fixed nav-failure handling + no-guilds return (see findings).
- [x] Review `src/theme.ts` — added `chip`/`inputBg` semantic tokens to SheetColors.
- [x] Review `src/sidebar.ts` — clean, no changes.
- [x] Review `src/sheets.tsx` — theme-aware colors, pager clamp, NFKC filter.
- [x] Review `src/index.tsx` — removed sendMessage fallback, wired nav boolean,
  clamped sheet title query, version fallback bump.
- [x] Review `scripts/build.mjs` + `scripts/check-manifest.mjs` — build now syncs
  manifest.version from package.json; check enforces manifest/package version match.
- [x] Regression tests added (96 → 102), CHANGELOG 4.5.10 entry, version bump.
- [x] **Checkpoint 2** — all of the above committed, `npm run verify` green.
- [ ] Optional remaining (small, deliberately skipped as low-value/risky):
  - `unwrapArgValue` could infinite-loop on a cyclic `{value: self}` arg (never
    seen in practice).
  - Guild names that are all digits (≥5) can't be excluded by name (parsed as id
    rule) — documented behavior in excludes format.
  - `resolveSwitchRow` fallback row uses hardcoded `#DBDEE1` (fallback path only).

## Findings log

- src/*.js — HIGH — stale tsc artifacts shadowed .ts sources, broke 2 test files — FIXED, ckpt 1
- command.ts jumpToGuild — MED — failed navigation still recorded recents + showed
  "Jumped to" success toast (deps.navigateToGuild returned void; failure invisible) — FIXED, ckpt 2
- index.tsx postCommandReply — MED (safety) — `sendMessage` fallback would post a
  real channel-visible message with the server list (dead code today, since the
  module is found by its `sendBotMessage` prop, but dangerous if ever live) — REMOVED, ckpt 2
- sheets.tsx — MED (UI) — hardcoded dark `#3A3C41`/`#1E1F22` on Close button,
  disabled pager, Filter input → unreadable in light theme — FIXED via new
  theme tokens, ckpt 2
- sheets.tsx pager — LOW — Prev/Next stepped from possibly-stale `page` state
  instead of clamped `safePage` — FIXED, ckpt 2
- sheets.tsx filter — LOW — not NFKC-normalized (inconsistent with /servers
  search for unicode names) — FIXED, ckpt 2
- utils/command — LOW — unbounded user query interpolated into pick-list header
  and no-match reply could exceed the 1900-char budget — FIXED (truncateForDisplay), ckpt 2
- command.ts — LOW — no-guilds path returned undefined → handleExec showed a
  second misleading toast — FIXED (returns error payload), ckpt 2
- build.mjs/check-manifest.mjs — MED (release) — build synced manifest hash but
  not version; check never compared manifest vs package version, so a bump could
  ship a manifest claiming the old version — FIXED, ckpt 2

## Verification commands

```sh
npm run verify   # typecheck + 102 tests + build + manifest check — all green as of ckpt 2
```

## Status: review COMPLETE. Remaining work is only the optional low-value items above.
