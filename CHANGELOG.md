# Changelog

## Versioning policy

- **Patch** (`x.y.Z`) — bug fixes, docs, internal refactors, no intentional user-facing behavior change.
- **Minor** (`x.Y.0`) — new user-visible features or settings that stay backward compatible.
- **Major** (`X.0.0`) — breaking changes to commands, settings keys, or install/update expectations.

Keep this file updated in the same PR/commit as the code. GitHub Releases should match the version section here. Move `[Unreleased]` notes into a version heading when tagging.

---

## [Unreleased]

- Expand C1/C4 detail in `OPTIONS.md` and require Risk on every backlog item

## 4.2.0

- Export / import custom aliases via clipboard (copy current list; merge from clipboard)
- Document changelog and semver policy
- Renumber `OPTIONS.md` with stable letter+number IDs (e.g. A1, C5)

## 4.1.0

- Show a pick list when multiple servers share the best search score instead of auto-jumping
- Theme-aware plugin settings colors (Discord semantic tokens with dark fallbacks)
- Debug Logging setting for Metro/patch/command diagnostics
- Document product backlog in `OPTIONS.md`
- Set plugin author Discord snowflake in `manifest.json` (follow-up on `main`)

## 4.0.0

- Extracted testable command/sidebar/utils modules
- Flat sidebar cache, pagination budget, alias and subsequence hardening
- Verify pipeline and CI
