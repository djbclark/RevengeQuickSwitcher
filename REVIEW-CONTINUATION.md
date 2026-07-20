# Code review continuation prompt (2026-07-19 session)

> **If resuming after an out-of-tokens cutoff, paste this to the new session:**
>
> "Continue the code review + fixup of RevengeQuickSwitcher described in
> REVIEW-CONTINUATION.md. Read that file first, pick up at the first unchecked
> item under 'Review plan', keep this file updated as you go, and commit a
> checkpoint after each batch of fixes. Focus on the non-QA plugin code
> (src/*.ts, src/*.tsx); ignore scripts/ (device QA automation). Verify with
> `npm run typecheck && npx vitest run` (and `npm run build`) before each commit."

## Ground rules established this session

- Scope: **plugin source only** — `src/*.ts`, `src/*.tsx`, build script if implicated.
  Explicitly OUT of scope: `scripts/` device-QA harness, VLM/OCR tooling, TESTING/VLM docs.
- Checkpoints = git commits on `main` after each verified batch of fixes.
- Baseline before this session: 96 vitest tests, typecheck green.
- HANDOFF.md has uncommitted edits ( M ) that predate this session — leave them
  staged-out of review commits unless they conflict (commit them separately or leave).

## Review plan / progress

- [x] **Checkpoint 0 — repo hygiene:** Stray `tsc` output (`src/*.js`, CommonJS
  compiled copies of the .ts sources) was untracked in src/ and **broke vitest**
  (2 test files failed because `src/theme.js` did a real
  `require("@revenge-mod/metro")` and won module resolution over `theme.ts`).
  Fixed: deleted `src/*.js`, added `src/*.js` to .gitignore, added
  `"noEmit": true` to tsconfig.json so a bare `tsc` can never emit into src/
  again. Tests back to 96 green. (commit: checkpoint 1)
- [ ] Review `src/utils.ts` (+ tests) — parsing, fuzzy match, shared helpers
- [ ] Review `src/aliases.ts`, `src/excludes.ts`, `src/recents.ts` (+ tests)
- [ ] Review `src/command.ts` (+ tests) — /servers command parsing/dispatch
- [ ] Review `src/theme.ts`, `src/sidebar.ts` (+ tests)
- [ ] Review `src/sheets.tsx` — switcher host UI (largest UI file)
- [ ] Review `src/index.tsx` — plugin entry, patches, settings (largest file, 855+ lines js-equiv)
- [ ] Review `scripts/build.mjs` + `scripts/check-manifest.mjs` (build correctness only)
- [ ] Apply fixes for confirmed findings, batch-committed with green verify each time
- [ ] Final: run full `npm run verify`, update this file's summary, final commit

## Findings log

(append findings here as: file:line — severity — description — fixed? commit)

- src/*.js — HIGH — stale tsc artifacts shadowed .ts sources, broke 2 test files — FIXED, checkpoint 1

## Verification commands

```sh
npm run typecheck && npx vitest run   # fast loop
npm run verify                        # full: typecheck + tests + build + manifest check
```
