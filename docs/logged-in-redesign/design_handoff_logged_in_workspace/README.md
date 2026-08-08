# Handoff: SpecIndex logged-in workspace

## Overview

The signed-in SpecIndex app, redesigned from a marketing page with filters bolted on into a working surface. Four screens: **Today** (what changed, what is new), **Discover** (everything the licence covers), **Pipeline** (a four-stage board of everything the user tracks), and the **Project record** (what we hold on a job, plus the user's own notes). The change this design makes: tracking a project now goes somewhere, and a rep can write down what they learned on a call without leaving the record.

Demo record throughout is **SPX-6700284, Maine State Prison Gatehouse Improvement Project** (Warren, Maine), pulled from the live public page at https://specindex.ai/project/me-portal-maine-vertical-3820/. It is a discovered project with no specification published, so it exercises every empty state honestly.

## About the design files

The files in this bundle are **design references created in HTML**. They are prototypes showing intended look and behavior, not production code to copy. The task is to **recreate these designs in the target codebase's existing environment** (React, Next.js, whatever specindex.ai runs on) using its established patterns, component library, and routing. If no environment exists yet, pick the framework that suits the project and implement there.

`SpecIndex Logged In.dc.html` is a streaming component format: the markup sits inside `<x-dc>` and the state lives in a `class Component` at the bottom of the file. Read it for structure, values, and copy. Do not port the format itself.

## Fidelity

**High fidelity.** Colors, type, spacing, and copy are final and should be matched. Interactions are real and clickable in the prototype: nav, territory expand, track/untrack, stage moves, tab switching, note entry. All data is illustrative except the Maine State Prison record, whose facts came from the live page.

---

## Design tokens

### Color

| Token | Hex | Use |
| :-- | :-- | :-- |
| Green 700 | `#0E4227` | Active nav text, button hover |
| Green 600 | `#16643A` | Primary brand, buttons, active accents, "The read" panel |
| Green 400 | `#6FA987` | Logo third bar |
| Green 100 | `#E7EFE9` | Active nav background, green tag background |
| Green 050 | `#EFF6F1` / `#F3F8F5` | Tracking pill, tracked card background |
| Green border | `#C6DDCF` | Tracked-state borders |
| Green on dark | `#A8CDB8` / `#C4DDCF` | Labels inside the green panel |
| Amber 600 | `#C0631A` | Mid-score numbers, notification dot |
| Amber 700 | `#A2601C` | Amber tag text, urgency copy |
| Amber 050 | `#FBF2E6` | Amber tag background |
| Amber border | `#E9DDCD`, bg `#FCF8F2` | Warning callouts (PRD) |
| Ink | `#111512` | Primary text |
| Ink 700 | `#3D4A42` | Secondary strong |
| Ink 600 | `#4B554E` | Body |
| Ink 500 | `#5B655E` | Muted body |
| Ink 400 | `#6B756E` / `#7A857E` | Meta text |
| Ink 300 | `#8A938C` | Labels, hints |
| Ink 200 | `#9AA39D` / `#A6AEA9` | Timestamps, disabled |
| Line | `#E4E7E3` | Default border |
| Line light | `#EFF1EE` / `#F2F4F1` / `#EDF0EC` | Row dividers, track backgrounds |
| Line dashed | `#D6DBD5` | Empty column outline |
| Surface | `#FFFFFF` | Cards |
| Surface raised | `#FBFCFB` | Sidebar, note composer |
| Canvas | `#F5F6F4` | App background |
| Column | `#EFF1EE` | Pipeline column background |
| Selection | `#D8EADF` | `::selection` |

Stage colors: Watching `#8A938C`, Specifier engaged `#C0631A`, Spec named `#16643A`, Closed out `#5B655E`.

Score color rule: `>= 70` green `#16643A` on `#E7EFE9`; `60 to 69` amber `#C0631A` on `#FBF2E6`; `< 60` grey `#5B655E` on `#F0F2EF`; `null` grey `#9AA39D` on `#F0F2EF` rendered as `--`.

### Typography

Geist (400, 500, 600, 700, 800) and Geist Mono (400, 500), both from Google Fonts. Body default 13.5px.

| Role | Family | Size | Weight | Letter-spacing |
| :-- | :-- | :-- | :-- | :-- |
| Page title (Today greeting, Pipeline) | Geist | 26px | 800 | -0.03em |
| Project title | Geist | 24px | 800 | -0.025em |
| "The read" statement | Geist | 18px | 700 | -0.02em |
| Section heading | Geist | 16px | 700 | -0.02em |
| Card heading / panel title | Geist | 14.5 to 15.5px | 700 | -0.015em |
| Pipeline card title | Geist | 13.5px | 700 | -0.01em |
| Body | Geist | 13 to 14px | 400 | normal |
| Nav item | Geist | 13.5px | 500, active 600 | normal |
| Eyebrow / label | Geist Mono | 10 to 11.5px | 400 | 0.07 to 0.09em, uppercase |
| Numeric (values, counts, IDs, dates) | Geist Mono | 11 to 13px | 400/500 | normal |
| Big stat (read panel) | Geist | 22px | 800 | -0.02em |
| Score, project rail | Geist | 28px | 800 | -0.03em |

### Spacing, radius, effects

- Radii: 4px (keyboard hint), 5 to 6px (tags, small buttons), 7px (nav, small controls), 8px (buttons, search, tabs), 9 to 10px (inner cards, composer), 12px (cards, panels), 999px (pills, state chips).
- Card padding: 15 to 22px. Panel padding 16 to 17px. Row padding 11 to 14px vertical, 15 to 18px horizontal.
- Grid gaps: 8 to 10px inside lists, 14px between board columns, 16 to 24px between major regions.
- Shadow: only one, on the active segmented pill: `0 1px 2px rgba(17,21,18,0.09)`.
- Sticky top bar: `rgba(245,246,244,0.94)` with `backdrop-filter: blur(8px)`, bottom border `#E4E7E3`.

---

## Layout shell

Two-column grid: `232px` sidebar, `minmax(0, 1fr)` main. Sidebar is `position: sticky; top: 0; height: 100vh`, background `#FBFCFB`, right border `#E4E7E3`, and a vertical flex column.

Main content is capped at `1180px` (Pipeline at `1320px`) centered, `30px` horizontal padding.

### Sidebar, top to bottom

1. **Logo lockup** (17px 16px 13px): three stacked 3px bars in an 18px column, colors `#16643A`, `#16643A` (offset 4px left margin), `#6FA987`, then wordmark "Spec" at 800 and "Index" at 600 `#3D4A42`, 16px, -0.02em. *Replace with the real SpecIndex ribbon-fold mark from the brand system.*
2. **Territory control**: full-width button, white, 1px `#E4E7E3`, radius 9px. Green 7px dot, mono uppercase "Territory" label at 9.5px `#8A938C`, value at 13px 600. Caret glyph right. Expands to a panel of state chips (24px tall, radius 999px, selected = green border + `#E7EFE9` + `#0E4227`).
3. **Nav**: Today, Pipeline, Discover. 33px tall, radius 8px, active `#E7EFE9` / `#0E4227` / 600. Right-aligned mono count, `#16643A` when active else `#9AA39D`. Pipeline count is the live tracked count.
4. **Saved views**: header row with a mono uppercase label and a 20px `+` button (radius 5px, `#E4E7E3` border, hover green) that starts the save-a-view flow. Below it, 30px rows with a mono count badge. Four seeded views; newly saved views prepend to the list.
5. **Account row**: top border, 28px green avatar circle with initials, name at 12.5px 600, "Territory licence" at 11px `#8A938C`.

### Top bar

56px tall. Left: current page title, Geist 15px 700. Center: search field, max 380px, 32px tall, white, radius 8px, placeholder "Search projects, owners, brands", trailing `/` key hint. Right: pill button "Pipeline · N", 31px, radius 999px, `#EFF6F1` on `#C6DDCF`, text `#16643A` 600.

---

## Screen 1: Today

**Purpose:** the landing screen after sign-in. What changed on my projects, then what is new and early enough to influence.

Header block: mono uppercase date eyebrow in green, greeting at 26px 800, one line of body at 14px `#5B655E` capped at 580px.

Body grid: `minmax(0, 1fr) 320px`, 24px gap, `align-items: start`.

### Left column

**Changed on your tracked projects.** Section heading plus an inline "View pipeline" text button. One white card, radius 12px, rows divided by `#F2F4F1`. Each row: a mono type tag (Spec amber, Doc green, Team grey, New amber), headline at 14px 600, project name at 12.5px `#7A857E`, right-aligned relative time in mono. Whole row is clickable and opens the project.

**New in {territory}, spec still open.** Heading plus a segmented control (`#EBEEE9` track, 3px padding, active pill white with the one shadow): "Spec still open", "Bid opens soon", "Rival named". To its right, a "Save this view" button (30px, white, `#E4E7E3`, hover green border and text).

**Save-a-view composer.** Replaces the Save button while open: green-tinted box (`#F3F8F5` on `#C6DDCF`, radius 10px, `12px 14px`). Mono uppercase "SAVE AS A VIEW", then a 33px name input pre-filled with a generated name (`{Territory} · {filter}`), a green "Save view" button, and a quiet Cancel. Enter saves, Escape cancels. Helper line: "Saves the current territory and filter. It appears in the sidebar and re-runs every time you open it." On save, a green confirmation strip appears naming the view, and clears after about 3 seconds.

**Selection bar.** Appears above the list whenever one or more rows are checked: white on a 1px `#16643A` border, radius 9px. "N selected", a Clear button, and a green "Track N projects" button that tracks all of them at Watching and clears the selection.

Each project row carries a 17px checkbox at its left edge (radius 5px, `#D6DBD5` border unchecked, filled `#16643A` with a white check when selected).

Project rows are separate cards, 10px apart, `15px 17px` padding, flex with 16px gap:
- 44px score block: number in the score color on its tinted background, radius 8px, 6px vertical padding, with a mono "SCORE" caption at 9px underneath.
- Body: title 15px 700 (hover `#16643A`), meta line 12.5px `#6B756E`, CSI division chips in mono 11px on `#F2F4F1` radius 5px, source line 12.5px `#8A938C`.
- 128px right rail: urgency line (amber `#A2601C` when urgent, else `#7A857E`), value in mono 13px, then the Track button. Untracked = solid green; tracked = "Tracking" in `#EFF6F1` on `#C6DDCF`.

Below the list: one muted line explaining the ranking.

### Right column (320px)

- **Your notes**: first card in the rail, green-bordered. The three most recent notes across all projects, each showing kind chip, timestamp, note text, and the project it belongs to. Clicking opens that project. Footer: "What you know about a job lives here, not in a CRM nobody opens."
- **Your pipeline**: one row per stage with its color dot, label, and count. Each row jumps to the board. Footer line: "Cards move when you say so, not when a crawler guesses."
- **Brand mentions**: card with header and three entries; each has a color dot (green = your brand, amber = rival), brand at 13px 600, mono relative time right, one line of context.
- **Data freshness**: three source classes with mono timestamps and a 3px progress bar (`#EDF0EC` track). Green when fresh, amber when stale. Showing a stale bar is intentional.

---

## Screen 2: Discover

**Purpose:** every project the licence covers, in one place. Today is short by design; this is where a user goes to see the whole entitlement.

Header: title 26px 800 ("Everything in Maine"), one line stating the covered count.

Controls row: segmented control with All 412 / Spec still open / Discovered, no spec / Bid opens soon, plus the same "Save this view" button as Today. The selection bar behaves identically.

Table: white card, radius 12px. Grid columns `17px 34px minmax(0, 1fr) 120px 92px 92px`, 14px gap, `12px 16px` row padding, rows divided by `#F2F4F1`. Header row on `#F7F8F6`, mono uppercase labels at 10px.

- Checkbox: same 17px control as Today.
- Score chip: mono 12.5px, 34px wide, centered, tinted by the score rule; `--` when unscored.
- Project: name 13.5px 600 (hover `#16643A`, opens the record), meta 12px `#8A938C`.
- Stage: mono uppercase chip, amber for active bid stages, grey for discovered.
- Value: mono 12.5px, right-aligned.
- Track: 27px button, same tracked/untracked treatment as Today.

Footer row: "Showing 8 of 412. Scroll loads the rest." In production this is infinite scroll with a sticky header row, default sort by priority score.

---

## Screen 3: Pipeline

**Purpose:** everything the user tracks, by where it sits in the spec window.

Header: title 26px 800, one line of body copy.

Board: `repeat(4, minmax(0, 1fr))`, 14px gap, `align-items: start`. Each column is a `#EFF1EE` block, radius 12px, 11px padding, with a header row (stage dot, label 13px 600, mono count) and 8px-gapped cards.

Card: white, 1px `#E4E7E3`, radius 10px, 12px padding.
- Title 13.5px 700, clickable, hover `#16643A`.
- Meta 12px `#7A857E` (city and owner).
- Row of mono chips: score (tinted by score color), value, and "N notes" when notes exist (`#F0F2EF`).
- Urgency strip when the project is time-critical: amber text on `#FBF2E6`, radius 6px, 5px 8px.
- Footer controls: `←` and `→` (28x26px, white, `#E4E7E3`) move the card one stage; a flex-filling green-tinted "Add note" opens the project record; a compact `×` untracks.

Empty column: dashed `#D6DBD5` outline, radius 10px, centered 12.5px `#8A938C` copy. The Watching column reads "Track a project from Today and it starts here."

**Rule:** stage is user-set only. Automated data updates the project record, never the card position.

---

## Screen 4: Project record

**Purpose:** what we hold on this job, what is missing, and what the user did about it.

Back link at the top returns to whichever screen the project was opened from ("← Back to today" / "← Back to pipeline").

Grid: `minmax(0, 1fr) 300px`, 24px gap. Right rail is `position: sticky; top: 74px`.

### Header card

Status tag (mono uppercase, amber on `#FBF2E6`) plus sector line. Title 24px 800 capped at 620px. Mono line: `{SPX id} · source pulled {date}`. Location at 13.5px.

**The read** panel: `#16643A`, radius 12px, `18px 20px`. Mono uppercase "THE READ" in `#A8CDB8`, then one sentence at 18px 700 stating the single most useful fact. Three stat tiles below on `rgba(255,255,255,0.09)`, radius 9px: value 22px 800, label 12px `#C4DDCF`.

**Facts grid**: four columns, mono uppercase labels, values at 13px. Missing values render in `#9AA39D` with the literal source language ("Not stated in the source record", "Unassigned, pre-award"), never a dash or a guess.

### Tabs

Executive brief, Scope, Specification, Team, Documents. 34px tall, radius 8px, active `#EFF1EE` with 600 weight; each carries a mono count badge. Panel body: title 15px 700, intro paragraph, then rows in 1px `#EDF0EC` boxes with a left label, a right value, and an optional tag (Yours/Cited/Parsed green, Extended/Rival/Upcoming amber, Gap/Past grey).

### Notes panel (the CRM piece, and the primary call to action)

Sits directly under the header card and ABOVE the document tabs. White card with a green `#C6DDCF` border and a 1px soft shadow, `18px 20px`. Placement is deliberate: notes are the reason the licence renews, so they are never at the bottom of the page.
- Header: "Log what happened", mono note count, and right-aligned "Private to your territory licence" at 12px `#9AA39D`.
- Composer: `#FBFCFB` box, 1px `#E4E7E3`, radius 10px. Borderless textarea, min-height 62px, placeholder "What happened on the call, who you spoke to, what to do next". Footer row: mono hint "⌘ + Enter to save" and a green "Save note" button.
- Entries: 2px `#E4E7E3` left rule, 13px left padding. Header line = kind chip (mono, `#F0F2EF`), author initials, mono timestamp right. Body 13.5px `#4B554E`, line-height 1.6.
- Empty state: "No notes yet. The first one also starts tracking, so the project lands in your pipeline."

### Right rail

1. **Track card**: green-tinted and green-bordered when tracked, plain white when not. Untracked shows one line of copy and a full-width "Track this project" button. Tracked shows four stage radio rows (selected = green border, 600 weight), then "Back to pipeline" and a quiet "Untrack".
2. **Priority score**: number at 28px 800 in the score color (or `--` in `#9AA39D`), mono "/100", mono uppercase caption, then three component bars: Spec openness, Divisions you sell, Timing. Unscored projects show flat `#D6DBD5` bars and the label "not scored".
3. **Activity**: sourced events only, each with title 12.5px 600, mono date, and the source name at 12px `#7A857E`. Footer: "Every line links to the public record it came from." Keep this visually distinct from notes.

---

## Interactions and behavior

| Trigger | Result |
| :-- | :-- |
| Sidebar nav click | Switch screen. All four screens render |
| Discover filter | Swap the segmented filter (the prototype shows the full list in every state) |
| Territory button | Toggle the state chip panel. Selection filters every screen (single territory in the prototype) |
| Top bar Pipeline pill / "View pipeline" / a stage row | Go to the Pipeline board |
| Track on a Today row | Track at stage `watching`. Clicking again untracks |
| Row checkbox | Toggle selection; the selection bar appears at one or more |
| Track N projects | Track every selected project at `watching`, then clear the selection |
| "Save this view" or sidebar `+` | Open the composer with a generated name pre-filled |
| Enter / Save view | Prepend the view to the sidebar list, show the confirmation strip, clear after ~3s |
| Escape / Cancel | Close the composer without saving |
| Project title click | Open the project record and remember the origin screen |
| Back link | Return to the origin screen |
| `←` / `→` on a card | Move one stage, clamped at both ends |
| Untrack (card or rail) | Remove from tracked; the card disappears from the board |
| Stage row in the rail | Set that stage directly |
| Tab click | Swap the tab body; content is derived from the project record |
| "Add note" on a pipeline card | Open the project record, where the composer sits above the tabs |
| Save note (button or Cmd/Ctrl + Enter) | Prepend the note, clear the composer, and auto-track the project at `watching` if untracked. Empty and whitespace-only input is ignored |

Hover states: rows and cards lift to `#FAFBFA` or border `#C9D3CD`; nav to `#EFF1EE`; primary buttons to `#0E4227`; titles to `#16643A`. No animation beyond default color transitions.

A saved view stores the territory and filter state only. In production it should re-run its query on open and keep its count fresh; phase 2 adds an email digest per view and a standing "track everything in this view" rule.

Not built in the prototype, needed in production: loading skeletons, error states, search results, saved-view rename and delete, note editing and deletion, optimistic-save failure handling, and responsive breakpoints (the grid needs a single-column fallback below roughly 1100px, and the sidebar should collapse to a drawer on mobile).

---

## State

| State | Shape | Notes |
| :-- | :-- | :-- |
| `tab` | string | Today, Discover, Pipeline, Project |
| `openId` | string | SPX id of the project being viewed |
| `from` | string | Origin screen, drives the back link |
| `detailTab` | string | Active project tab |
| `filter` | string | Today segmented control |
| `discoverFilter` | string | Discover segmented control |
| `territoryOpen` | boolean | Sidebar state panel |
| `tracked` | `{ [spxId]: stageKey }` | Server-persisted per user in production |
| `notes` | `{ [spxId]: Note[] }` | `Note = { id, who, when, kind, text }` |
| `draft` | string | Note composer text |
| `selected` | `{ [spxId]: true }` | Row selection for bulk track |
| `savedViews` | `{ name, badge }[]` | Sidebar list; new views prepend |
| `creatingView` | boolean | Save-a-view composer open |
| `viewDraft` | string | View name input |
| `justSaved` | string | Name shown in the confirmation strip, cleared on a timer |

Stage keys: `watching`, `engaged`, `specified`, `closed`.

Data fetching in production: Today needs a change feed scoped to tracked ids, a scored list scoped to territory, brand mentions, and pipeline freshness. The project record needs the project, its documents/divisions/manufacturers, its sourced activity, and the user's notes. Notes are a write path scoped to the licence, never public, and never fed to model training.

---

## Content rules that are load-bearing

1. Never fabricate a value. If the source record does not state it, print the source's own language.
2. An unscored project shows `--`, not `0`.
3. Notes and sourced activity must never be visually confusable.
4. No marketing copy on any signed-in screen.
5. No em dashes anywhere in the product copy.

---

## Assets

No images. The logo is a placeholder three-bar mark drawn in CSS; replace it with the real SpecIndex ribbon-fold lockup from the brand system. Fonts load from Google Fonts (Geist, Geist Mono).

---

## Files in this bundle

| File | What it is |
| :-- | :-- |
| `SpecIndex Logged In.dc.html` | The interactive design. Open in a browser; all three screens are clickable |
| `Logged-In Workspace PRD.dc.html` | The PRD: scope, requirements per screen, risks, definition of done. Printable to PDF |
| `support.js` | Runtime for the two HTML files. Not part of the design |
| `doc-page.js` | Print shell used by the PRD. Not part of the design |
| `screenshots/` | 01 Today, 02 Discover, 03 Pipeline, 04 Project record |
