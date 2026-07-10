# OPTIONS — open work

> **For agents:** When the operator asks for **options** or **next steps**, read this
> file, present the open items **with descriptions and risk**, do any requested work,
> then **replace** this list (drop completed items; keep IDs stable). **Commit and
> push** in the same turn.
>
> Session context: [HANDOFF.md](HANDOFF.md). Dev setup: [HACKING.md](HACKING.md).
> Device checklist: [TESTING.md](TESTING.md). Release notes: [CHANGELOG.md](CHANGELOG.md).
> Strategic directions: [HANDOFF.md appendix](HANDOFF.md#appendix--strategic-directions).

**Plugin snapshot (2026-07-10):** Released on `main` as **v4.5.9** — top-docked
switcher, dismiss-then-`openUrl` jump, Copy debug logs. Unit gate: `make verify`
(96 tests). Cloud agents cannot reach the phone; **A1** is the human/device gate.

**Risk scale:** **Low** = mostly our code / storage / docs · **Medium** = Metro/UI
discovery with graceful fallbacks · **High** = deep Discord internals; easy to
break on client updates · **Latent** = only act if a symptom returns.

**Suggested agent order:** close or drive **A1** (device QA) before new features;
prefer **C4** (pins) over **C2**/**C3** (high Metro surface). Do not reintroduce
Flux/`selectChannel` jump paths or full-screen scrims (see HANDOFF).

**How to reference:** say **A1**, **C4**, **D1**, etc. Keep IDs stable forever;
when an item ships, move it to **Closed** (do not renumber).

---

## Pick a track

| Track | Focus | Open IDs | Typical risk |
|-------|-------|----------|--------------|
| **A — Device QA** | Revenge client checklist | A1 | Low (process); blocks confidence in sheet/nav |
| **B — Switcher polish** | Pins and list UX on stable sheet | C4 | Low–Medium |
| **C — High-risk Metro** | Channels / folder-aware sidebar | C2, C3 | Medium–High |
| **D — Engineering** | Harness / smoke | D1 | Low |
| **E — Latent follow-ups** | Only if a symptom returns | C1b | Latent / Medium–High |

---

### Track A — Device QA

#### A1 — Device QA (human + agent assist) · Risk: **Low** (process)

Requires a Revenge Discord client and the checklist in [TESTING.md](TESTING.md).

**Retest on v4.5.9:**

1. Top-docked switcher stays **above** the Android keyboard while filtering.
2. After a server tap, jump lands and Discord taps still work (no dead UI).
3. Copy debug logs show `v4.5.9` and `openUrl` (not mixed older versions).
4. Close dismisses the panel; bot-message fallback still OK if sheet APIs missing.

Close **A1** when the operator signs off (or a future harness covers the same
assertions). Agents: prepare checklists / interpret log pastes; do not claim
pass from CI alone.

---

### Track B — Switcher polish

#### C4 — Favorites / pinned servers (agent) · Risk: **Low** (list-only) / **Medium** (flat sidebar)

User-chosen servers that always float to the top of `/servers` (and optionally
the flat sidebar), independent of A–Z order or recents.

**User-facing shape:**

- Settings: ordered pins by name/id, reorder, clear
- Switcher / list: pinned block first, then the rest A–Z
- Optional later: `/servers query:p1`-style shortcodes; export with aliases

**How:** store ordered guild IDs in plugin storage; partition pinned vs
unpinned when building the list; resolve names via GuildStore; drop/flag stale
IDs after leaving a server.

**Why:** aliases speed *search*; pins change *priority*. Complements recents
(**C1** / B8) without Metro guild-select hooks.

**Depends on:** sheet path stable (**A1** preferred first). Pairs with excludes
and alias export.

---

### Track C — High-risk Metro (explicit ask only)

#### C2 — Channel search / jump (agent) · Risk: **High**

Search and jump to channels, not only servers. Large Metro surface
(permissions, channel stores, navigation); breaks often across Discord
versions. May deserve a **separate plugin**. Do not start unless the operator
explicitly picks this.

#### C3 — Folder-aware (non-flat) sort (agent) · Risk: **Medium**

Keep Discord folders, but sort inside them and/or sort folder nodes — modes
beyond today’s all-or-nothing flat list. Folder node shapes vary; wrong
assumptions scramble the sidebar. Needs defensive parsing + device tests
(**A1**-style). Natural Flat Sidebar extension; still explicit-ask preferred.

---

### Track D — Engineering

#### D1 — Integration smoke / Metro self-check (agent) · Risk: **Low**

Document expected Metro props (`openUrl`, alert/sheet hosts, GuildStore, …).
Optional runtime self-check when debug logging is on. Worst case: noisy logs,
not broken navigation. Optional later: thin Handsets-driven QA (stayturgid
research) — Vitest remains the default `make test`; do not Appium-first.

---

### Track E — Latent follow-ups (symptom-driven)

#### C1b — Auto-track recents via guild-select hooks (agent) · Risk: **Latent / Medium–High**

Shipped recents (**C1** / B8) only record when *this* plugin navigates. A
follow-up could hook Discord “current guild” / select modules for automatic
history. **Do not start** without a clear product ask — high churn, easy to
freeze (see v4.5.x saga in HANDOFF). Trigger: operator wants sidebar-driven
recents and accepts Metro risk.

---

**Non-goals / do-not-touch:**

- Faux DM or fake Discord server as the switcher UI (rejected in C8)
- Jump via loose `selectChannel`, Flux `CHANNEL_SELECT` / `GUILD_SELECT`, or
  `selectGuild` as primary path (use dismiss-then-`openUrl`)
- Full-screen touch scrims / nested RN `Modal` hosts that outlive the sheet
- Bottom `ActionSheet` as the **primary** searchable switcher on Android
  (keyboard covers it; top-dock is intentional)
- Renumbering shipped IDs; editing git history to “clean” Done items

---

**Closed (2026-07-10):** Docs HANDOFF / HACKING / README index (PR docs branch).

**Closed (v4.5.9 / B17–B18, C5, C8):** Top-docked switcher + dismiss-then-`openUrl`;
freeze/dead-tap saga; tappable disambiguation; dedicated sheet UI (not faux DM).

**Closed (v4.5.2–4.5.8):** Overlay dismiss iterations; Copy debug logs;
version-stamped ring; JumpTo `openUrl`; ActionSheet host experiment.

**Closed (v4.4.x / B9–B16, C7):** Excludes; install URL / IIFE / Hermes enable;
slash menu `shouldHide`; `sendBotMessage`; query jump replies.

**Closed (v4.1–4.3 / B1–B8, C1, C6, D2–D3):** Author id; pick-list; theme
settings; debug toggle; releases/changelog/semver; alias export-import;
low-risk recents.
