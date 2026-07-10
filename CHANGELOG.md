# Changelog

## Versioning policy

- **Patch** (`x.y.Z`) — bug fixes, docs, internal refactors, no intentional user-facing behavior change.
- **Minor** (`x.Y.0`) — new user-visible features or settings that stay backward compatible.
- **Major** (`X.0.0`) — breaking changes to commands, settings keys, or install/update expectations.

Keep this file updated in the same PR/commit as the code. GitHub Releases should match the version section here. Move `[Unreleased]` notes into a version heading when tagging.

---

## [Unreleased]

_Nothing yet._

## 4.5.7

- Fix dead taps after a successful jump: dismiss the switcher host fully before `openUrl`, prefer Discord’s action-sheet host (JumpTo’s `hideActionSheet` path), remove the full-screen touch scrim, and re-dismiss after navigation starts
- Device QA (v4.5.6): jump worked and chat scrolled, but all buttons were inoperable — leftover overlay shell

## 4.5.6

- Navigate via Discord deep links (`openUrl` + `https://discord.com/channels/{guild}/{channel}`), matching **aliernfrog/JumpTo** (Revenge Android–tested)
- Stop calling `selectGuild` / `GUILD_SELECT` (device log: both ran, selection did not stick, then freeze after the failure toast)

## 4.5.5

- Fix freeze after verified jump: stop dispatching Flux `CHANNEL_SELECT` (device logs showed store update then UI hang); prefer `selectGuild` / `transitionToGuild`, then `GUILD_SELECT` only
- Stamp plugin version on every debug log line (`[v4.5.5 …]`) and clear the ring on upgrade so Copy debug logs is not a mix of builds

## 4.5.4

- Fix complete freeze on server tap: stop calling loose `findByProps("selectChannel")` (device logs showed it hangs Discord) and remove the “unverified accept” success path
- Navigate via strict Flux `CHANNEL_SELECT` / `GUILD_SELECT`, then `selectGuild` / `transitionToGuild`; only toast jump success when SelectedGuildStore verifies the target (when readable)

## 4.5.3

- Fix guild jump freeze: stop chaining loose Navigation/Flux matches; use `selectChannel` / `selectGuild` / `transitionToGuild` only, and verify via SelectedGuildStore when possible
- Fix **Copy debug logs**: persist the ring across restarts, copy as a single clipboard-safe line (Discord was dropping newlines), and show a toast preview of the last event

## 4.5.2

- Fix stuck switcher overlay: remove nested RN `Modal`, hide panel locally on Close/pick, and dismiss via `dismissAlert` / `hideActionSheet` / legacy `close`
- Navigate to the picked server **after** the overlay closes so the guild UI can update
- Add **Copy debug logs** in plugin settings (ring buffer of recent switcher/nav events) for device QA without adb

## 4.5.1

- Dock the `/servers` switcher to the **top** of the screen (alert/modal overlay) so the virtual keyboard no longer covers it
- Add **Previous / Next** paging in the switcher (8 servers per page) with a scrollable page body
- Keep short ambiguous picks on the simple action sheet; full switcher prefers top panel

## 4.5.0

- **C8:** `/servers` opens a searchable switcher sheet (filter + recent + tap to jump); **Open switcher** button in plugin settings
- **C5:** Ambiguous search opens a tappable pick sheet instead of only a markdown list
- Keep bot-message / markdown fallbacks when Discord sheet APIs are unavailable
- Explicit `/servers page:N` still posts the paginated list in-channel

## 4.4.7

- Fix `/servers query:…` looking like a no-op: jumps/errors now post an in-channel bot reply (same path as the working page list)
- Harden option parsing for nested/positional Revenge/Discord arg shapes
- Try multiple guild navigation APIs (`transitionToGuild`, `selectGuild`, Flux `GUILD_SELECT` / `SELECT_GUILD`, nav push)

## 4.4.6

- Post `/servers` list/pick replies via `sendBotMessage` (same path as Revenge `/debug` ephemeral) so the list appears in-channel instead of silently failing
- Unregister any prior `/servers` registration before re-registering to avoid duplicate slash entries after reload

## 4.4.5

- Fix `/servers` never appearing in the slash menu: Revenge treats `shouldHide: () => false` as “hide” (`shouldHide?.() !== false`). Omit `shouldHide` so the command shows.
- Fill Vendetta/Revenge command metadata (`applicationId`, `type`, `inputType`, display names).
- Return `{ content }` from list/pick results so Revenge can post the reply.

## 4.4.4

- Fix main plugin enable after smoke succeeded: transpile bundle to ES2015 (strip `?.` / `??` / `??=` that older Hermes rejects at eval)
- Match Vendetta template globals (`vendetta.*` / `window.React`) instead of a custom IIFE param list
- Do not touch plugin storage at module eval time; never use `this` in `onLoad` (Vendetta calls it unbound)
- Soften onLoad/onUnload so secondary failures cannot flip the toggle to X
- Toast on successful load so enable is obvious on device

## 4.4.3

- Rebuild plugin in classic Vendetta IIFE shape used by known-working Revenge plugins
- Add `smoke/` minimal load-test plugin for isolating enable failures
- Document Revenge logging / debug surfaces for device QA

## 4.4.2

- Fix plugin failing to enable: register `/servers` with required `description`, isolate load errors
- Lazy/fallback settings switch so the wrench works after a successful start

## 4.4.1

- Fix Revenge install: use raw GitHub base URL (repo page URL cannot fetch `manifest.json`)
- Emit Vendetta-compatible plugin bundle with polymanifest `hash`
- Document correct install URL in README / TESTING

## 4.4.0

- Exclude / mute servers from search (by name, id, or `~partial`)
- Optional hide excluded servers from `/servers` list
- Device QA checklist updated for v4.4.0 human testing

## 4.3.0

- Low-risk recent-servers history: record only when this plugin jumps
- `/servers recent` list and `/servers rN` slot jump
- Settings for history size (1–15) and clear recent

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
