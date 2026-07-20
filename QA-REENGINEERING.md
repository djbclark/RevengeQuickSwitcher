# Device QA re-engineering plan (v2 harness)

> **Status:** proposal, 2026-07-19. Supersedes the D1 unblock approaches in
> [OPTIONS.md](OPTIONS.md) Track D if adopted. The v1 harness
> (`scripts/device_qa_qss.py` + stayturgid/Handsets) is considered a dead end
> for _driving_ the UI; parts of it are reused (see "What we keep").

## Diagnosis — why v1 can't touch the right places

The failures (voice-overlay hang, off-screen bounds, taps that "succeed" but do
nothing, coord taps that miss) all share one root cause:

**Targeting is open-loop.** The harness decides _where_ to tap from Handsets
accessibility dumps, and Discord is a React Native app whose custom surfaces
(voice overlay, sheets, modals) expose missing, stale, or off-screen
accessibility nodes. Vision (OCR gate, VLM) is only used to _verify after the
fact_ — it never _aims_. So the system can see, but it taps blind, and when the
dump lies there is no recovery: `tap_text` waits for a node that will never
appear (the `leave_voice_channel` hang).

Secondary problems:

| Problem                                                  | Consequence                                                                                                       |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| AI (cloud VLM) sits inside the control loop              | 2–8s per gate, non-deterministic pass/fail, flaky runs                                                            |
| Asserts read the screen for things the app already knows | Screenshot+OCR to detect "jump happened" when the plugin logs `navigateToGuild openUrl ok` internally             |
| Steps can block forever                                  | `tap_text` timeouts compound into the 600s hang                                                                   |
| Everything is a tap                                      | Even navigation that Android can do directly (deep links, keyevents, force-stop) goes through the fragile UI path |

On the "AI vs OCR designed for QA" hypothesis: partially right, with a twist.
Tesseract is _already_ good enough — the miss is that we only use its
**boolean output** (is this text present?) and never its **geometry** (word
bounding boxes → tap coordinates). Deterministic OCR-as-locator + template
matching is exactly what QA-grade vision automation (SikuliX/Airtest lineage)
does, and none of it needs a model in the loop.

## Design principles for v2

1. **Don't touch the UI unless there is no other way.** Prefer intents, deep
   links, keyevents, app lifecycle commands.
2. **Ground truth from inside the app, not from pixels.** The plugin can tell
   the harness what happened; the screen is a last resort.
3. **When we must tap, aim closed-loop:** screenshot → locate on _that_
   screenshot → tap → re-screenshot → confirm state changed → retry ladder.
4. **No AI in the control loop.** VLM is demoted to offline triage of failure
   artifacts. Every runtime decision is deterministic.
5. **Every step is (precondition, action, postcondition, deadline, recovery).**
   Nothing may block past its deadline; a failed postcondition triggers
   recovery or a clean abort with artifacts — never a hang.
6. **Safety policy carries over unchanged** (see below).

## Proposed architecture

### Layer 0 — Transport & input: FireRPA (lamda)

Replace the adb + Handsets sandwich with the FireRPA on-device agent (already
proven in another project):

- Stable RPC to the device (hierarchy, screenshots, input injection, app
  lifecycle) instead of ad-hoc `adb exec-out` + Handsets dumps.
- UIAutomator-level hierarchy from the _system_ side — often sees what
  Handsets' dump misses, and system surfaces (notification shade, permission
  dialogs) always have real nodes.
- Screenshots without the `screencap -p` corruption dance.

**Rule kept from v1 research:** one driver owns the device. FireRPA replaces
Handsets entirely for QSS QA — never run both against the same session.

**Spike question (Phase 0):** confirm FireRPA runs on the s24 (root/One UI
compatibility) and that its hierarchy shows the Discord voice overlay's
Disconnect control that Handsets couldn't find.

### Layer 1 — Navigation without taps

| Need                                 | v1 (taps)                      | v2 (no taps)                                                                                                                                                                                                                  |
| ------------------------------------ | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Go to a guild/channel                | Sidebar scroll + tap ladder    | `am start -a android.intent.action.VIEW -d "https://discord.com/channels/<guild>/<channel>"` — the exact path the plugin itself uses and that is device-proven                                                                |
| Reset app state                      | Navigate back N times          | `am force-stop app.revenge` + relaunch + deep link                                                                                                                                                                            |
| Leave voice channel (the v1 blocker) | `tap_text("Show Chat")` → hang | (a) deep-link to a text channel, then disconnect via the **ongoing-call notification action button** in the shade (system UI, real a11y nodes, reachable via FireRPA); (b) fallback: KEYCODE ladder with postcondition checks |
| Dismiss transient UI                 | Blind taps                     | KEYCODE_BACK with a screen-classifier postcondition after each press                                                                                                                                                          |

This alone removes most of the surface where v1 failed: if we never tap the
sidebar, its off-screen-bounds problem is irrelevant.

### Layer 2 — In-app ground truth: a QA bridge in the plugin

Small, version-gated addition to QSS (behind a `storage.qaBridge` flag, off by
default): mirror every debug-ring line to `console.log` with a grep-able
prefix (`QSSQA|<json>`). RN console output lands in logcat under
`ReactNativeJS`, so the harness asserts by reading
`logcat -s ReactNativeJS` for structured events:

- `command invoke`, `opened switcher UI`, `navigateToGuild openUrl ok`,
  `recordRecent` — all already exist in the ring; this only adds the mirror.
- Converts the majority of v1's vision asserts (did the jump happen? did the
  sheet open? was a recent recorded?) into instant, deterministic text asserts.
- No new data exposure: the ring already contains these lines; the bridge only
  changes where they can be read. Off by default; the harness turns it on via
  plugin settings storage and turns it off after.

### Layer 3 — Closed-loop vision targeting (only where taps remain)

Remaining tap targets (switcher rows, Filter field, plugin settings toggles)
get a **locator ladder**, each rung verified against a fresh screenshot:

1. **FireRPA/UIAutomator selector** (text/desc/resource-id) — if the node
   exists with sane on-screen bounds, use it.
2. **OCR word-box locator** — Tesseract TSV (word + bbox + confidence) on the
   current screenshot; tap the center of the matched phrase's box. This is the
   "OCR designed for QA" piece: same engine we already ship, now supplying
   coordinates instead of booleans. If Tesseract's hit rate on themed Discord
   text disappoints, swap in PaddleOCR behind the same interface — evaluate in
   the spike, don't rebuild around it.
3. **Template match** (OpenCV `matchTemplate`) for icon-only targets (red
   hang-up, emoji toggle): small library of reference crops per resolution,
   captured in both light and dark theme.
4. **Fail** with artifacts (screenshot + hierarchy + OCR TSV) — never a blind
   coordinate tap from a config file.

After _every_ tap: re-screenshot and check the expected state transition via
the screen classifier (below). A tap whose postcondition fails is retried once
down the ladder, then the step fails cleanly.

### Layer 4 — Screen classifier & orchestration

- Reuse `scripts/ocr_gate.py`'s check patterns (`discord_home`,
  `safe_test_channel`, `switcher_open`, …) as a **screen classifier**: cheap
  OCR fingerprint → named screen state. Run it as the pre/postcondition of
  every step.
- Rebuild the flow as explicit steps: `Step(name, precondition, action,
postcondition, deadline, recovery)`. A pytest scenario is a list of steps;
  the runner enforces deadlines with hard timeouts so _no step can hang the
  suite_ (the class of bug that killed v1 runs becomes structurally
  impossible).
- Report stays `report.json` + PNG artifacts per step, same layout as v1.

### Layer 5 — AI, demoted

Cloud VLM (and local UI-TARS) move entirely **out of the runtime path**. Their
only job: post-mortem triage — when a run fails, an agent looks at the failure
artifacts and drafts a diagnosis. No `QSS_VLM` gate in the loop; `QSS_VLM`
env becomes triage-only.

## What we keep from v1

- **The safety policy, unchanged and mandatory:** `QSS_SAFE_MODE` semantics,
  DM-thread block, allowlisted typing only (Filter field, install URL),
  settings-path-first (slash only behind `QSS_ALLOW_SLASH=1`). Typing now also
  requires the screen classifier to positively identify an allowlisted input
  surface _from the current screenshot_ before injection.
- `scripts/ocr_gate.py` check patterns (become the screen classifier).
- Artifact layout (`artifacts/qss-qa/<date>/<device>/`), `report.json` shape.
- The device lessons table in OPTIONS.md (bounds checks, half-screen scrolls)
  — as review checklist for the new locators, not as coordinate constants.

## Phases

**Phase 0 — Spike (½–1 day, kill-or-commit):**

1. FireRPA agent on the s24; hierarchy + tap + screenshot round-trip.
2. Reproduce the v1 killer: device parked in the Stream Room voice overlay.
   Prove **any** of: (a) FireRPA hierarchy exposes Disconnect; (b) notification
   shade action disconnects; (c) deep-link nav works while the overlay is up.
3. OCR word-box POC: locate and tap "Filter servers" purely from a screenshot.

- **Kill criteria:** FireRPA won't run on this device, or none of 2(a–c)
  works. Then fall back to the same architecture on plain adb (uiautomator
  dump + input tap) — the layers above don't actually require FireRPA, it's
  just the best transport.

**Phase 1 — QA bridge in the plugin** — **DONE, shipped in v4.6.0** (2026-07-19):
`src/qabridge.ts` (format + parser contract, unit-tested), mirror wired into
`debugLog` behind `storage.qaBridge` (off by default), settings toggle "QA
Bridge (mirror debug log to logcat)". Harness greps
`adb logcat -s ReactNativeJS` for `QSSQA|<json>` lines.

**Phase 2 — Harness core:** new `scripts/qa/` driver implementing layers 1–4.
**Device-free core landed 2026-07-19** (uv project, `cd scripts/qa && uv run
--group dev pytest`): `qss_events.py` (logcat bridge parser, version-pinned),
`step_runner.py` (deadline-enforced steps — a hung action is abandoned at its
deadline, verified by test), `ocr_locator.py` (Tesseract TSV → phrase → tap
center, pure logic + thin `ocr_tsv()` shell). **Remaining (needs device):**
FireRPA transport binding, deep-link nav actions, screen classifier port, and
the ported `wait_discord_ready` / switcher scenarios asserting logcat-first.

**Phase 3 — A1 as code:** encode the TESTING.md device checklist as pytest
scenarios; `just qa` runs it end-to-end; v1 `device_qa_qss.py` is archived
(not deleted) once v2 passes A1 twice consecutively.

## Open questions

1. Was FireRPA's working setup (other project) on this same s24 / same root
   state? If not, Phase 0 item 1 is the real gate.
2. Does Discord's ongoing-call notification expose a Disconnect action on
   One UI 6? (Phase 0 item 2b.)
3. Tesseract vs PaddleOCR hit rate on Discord's fonts/themes — measure in
   Phase 0 item 3 before committing.
4. Deep links while the app is cold vs warm: does `am start -d` route
   correctly from a killed state? (v1 evidence says relaunch reconnects to
   voice — the deep link may need to land _after_ `wait_discord_ready`.)
