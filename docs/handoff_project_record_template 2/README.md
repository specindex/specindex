# Handoff: SpecIndex project record page, one template for two record depths

Target route: `/projects/[slug]`

Reference records:
- `/projects/me-portal-maine-vertical-3820` — deep record, has a 219 page spec book
- `/projects/ga-hyundai-sk-battery-bartow` — shallow record, no documents at all

## What this is

A redesign of the public project record page, built as **one template that must render
both records correctly**. That constraint is the whole point of the package. The current
page works when a project has documents and falls apart when it doesn't.

`Project Record Template v3.dc.html` is a **design reference written in HTML**, not
production code. Open it in a browser. It has a Compare toggle at the top left that swaps
between the Maine and Hyundai-SK records live. Flip it repeatedly while you build — every
layout decision in here exists to survive that flip.

Recreate it in the specindex.ai codebase using the app's existing framework, routing and
data layer. Do not port the inline styles verbatim; map them to whatever styling system the
app already uses. The file uses a small internal template runtime (`<sc-if>`, `{{ }}` holes,
a `Component` class) — ignore that machinery, only the structure, copy and style values matter.

## Fidelity

**High fidelity on layout, type and color.** The palette is the locked SpecIndex brand
palette, not a suggestion.

**The Maine data is real and verified.** It was read directly from the 219 page project
manual, included at `reference/3820_Specifications_DOC_MSP.pdf`. Every page citation in the
design can be checked against that PDF. The Hyundai-SK data is transcribed from the live
production page.

---

## The core problem this template solves

SpecIndex has two kinds of record and they are not variations of each other:

| | Maine (deep) | Hyundai-SK (shallow) |
|---|---|---|
| Documents held | 6, incl. 219pp spec book | 0 |
| Spec citations | 20, all page-cited | none possible |
| Divisions | 16, from the manual's TOC | 4, described |
| Team | 4 roles, 2 contacts | 5 roles, 4 contacts |
| Priority score | pending | 15/100, Low signal |
| Value / sq ft | not published | $5B / 3.3M sq ft |

A record with no documents is **not a broken record**. It is a discovered project where the
specification has not been written yet. The design has to say that plainly and then pivot to
what the user can act on — which for Hyundai-SK is a fully mapped construction team.

Every empty state in this design is written, not blank. Never ship a bare card.

---

## Page structure

Max width **1320px**, horizontal padding **32px**, page background `#F6FAF7`.

1. Sticky header (62px)
2. Grounding strip (breadcrumb row + AI provenance chips + Compare toggle in the prototype)
3. Two-column body: main + sticky right rail
4. Footer

```
display: flex; flex-wrap: wrap; gap: 26px; align-items: flex-start;
main  → flex: 1 1 660px; min-width: 0
aside → flex: 1 1 300px; position: sticky; top: 86px
```

All internal grids use `repeat(auto-fit, minmax(Npx, 1fr))`. No media queries needed.
Main sections stack with 16px gap. Section card:
`background #FFFFFF, border 1px solid #DEEAE3, border-radius 16px`.

**The Compare toggle is a prototype device only. Do not build it.** It exists so a reviewer
can flip records without two browser tabs.

---

## 1. Hero section

Padding `28px 30px 26px`. Three parts: identity block, score card, the read panel.

### Identity (left, `flex: 1 1 340px`)
- Status pill + sector on one row.
  - `Bidding` → amber: `#0C1524` on `#FDF0D6`, 1px `#F59E0B`, radius 999px, 11.5px/700/uppercase/1.3px.
  - `Under construction` → grey: `#5B6A79` on `#F6FAF7`, 1px `#DEEAE3`.
- H1: Space Grotesk 700, **35px**, line-height 1.09, letter-spacing `-1.1px`, `text-wrap: pretty`.
- ID line in monospace 12.5px `#5B6A79`: internal ID + source pull date.
- Location, 14.5px.

### Priority score card (right)
A button. Clicking expands the breakdown inline below the hero.

- Score: Space Grotesk 700, 31px, `-1.4px`, followed by `/100` in monospace 12px `#5B6A79`.
- Label `PRIORITY SCORE`, 10.5px/700/uppercase/1.3px `#5B6A79`.
- Signal line: colored dot + text. `Low signal` uses `#8A9AA8`; a strong signal uses `#166534`.
- Card border goes `#DEEAE3` → `#2F9E5C` when expanded.

**Breakdown panel** (`#F6FAF7`, 1px `#DEEAE3`, radius 12px): five factor rows, each with a
label, a one-line detail, a 6px progress bar (128px wide, track `#DEEAE3`, fill `#2F9E5C` at
≥70 / `#A6BBAF` below / `#C3D8CB` at zero) and a right-aligned value word.

> **The five factors in the prototype are a layout placeholder, marked as such in the UI.**
> Wire them to the real scoring model. Keep the placeholder treatment until you do — an
> invented score shown as fact is worse than no score. Maine's score renders `--` / "Not
> pulled" for the same reason; Hyundai-SK's 15/100 is real, from production.

Copy that must survive: *"Score reflects how much you can act on, not how big the job is. A
small job with a spec book outranks a large one without."* That sentence is why a $5B plant
scores 15.

### The read panel

One or two sentences telling the user what this record means, plus three stats. **It inverts
by record depth:**

- **Has documents** → forest `#166534` panel, white text, stat tiles `rgba(255,255,255,0.09)`,
  eyebrow `#A6BBAF`, body `#D2E7DB`.
- **No documents** → light panel `#F6FAF7` with 1px `#DEEAE3`, ink text, white stat tiles,
  numbers in `#166534`.

A record with nothing cited does not get the dark hero treatment. The visual weight has to
match the substance, or every record looks equally authoritative and none of them are trusted.

Structure: eyebrow "THE READ" → 21px Space Grotesk 600 headline → three stat tiles
(`flex: 1 1 172px`) → a footer line above a hairline rule carrying the single sharpest fact.

Maine's footer quotes General Conditions 17.1. Hyundai-SK's names the route in via the team.
A zero stat renders in `#8A9AA8`, not the accent color.

### Facts grid

`repeat(auto-fit, minmax(165px, 1fr))`, 1px gap on a `#DEEAE3` background so the hairlines
are the grid itself. Cells are white, padding `14px 16px`. Label 10.5px/700/uppercase/1.3px
`#5B6A79`, value 14.5px/600.

**Takes any number of fields.** Maine shows 9, Hyundai-SK 8, and they are different fields.
A missing value renders as `Not stated in the source record` in `#5B6A79` — visible, never
omitted, never guessed.

---

## 2. Tab section

Tab order is deliberate — it follows the user's own question sequence:

**Executive brief → Scope → Specification → Team → Documents**

*Is this worth my time* → *is my division even in it* → *am I named and who is* → *who do I
call* → *prove it*. Scope precedes Specification because relevance gates everything: a Div 26
rep needs to know electrical is in scope before a citation list means anything. Documents is
last because it is the proof layer, reached when someone doubts a claim.

Executive brief is the default landing tab.

Tab bar: white, `border-bottom: 1px solid #DEEAE3`, buttons `padding: 16px 13px`, 14.5px/600.
Active is `#0C1524` with `box-shadow: inset 0 -2px 0 #166534`; inactive `#5B6A79`. Each tab
carries a count pill in monospace 11px. **A zero count renders greyed, never hidden** — the
absence is information.

### Executive brief
Heading "Executive brief" in Space Grotesk 700 19px, then paragraphs at 16px/1.7, max 76ch.
Attribution line below a hairline in monospace 12px.

Served verbatim from the record. Do not truncate or re-summarize.

### Scope

Intro line, then a card grid `repeat(auto-fit, minmax(300px, 1fr))`.

**Sort divisions that name nobody FIRST.** This is the most important behavior on the tab.
Maine has 16 divisions and 8 name no manufacturer at all — including Plumbing, HVAC and
Electrical. Those eight are the entire reason a mechanical or electrical rep would care, and
in the current production page they are invisible.

Card: code + tag chip on top, then division name in Space Grotesk 700 15.5px, then detail.
- Names nobody → 1px `#2F9E5C`, background `#EDF5F0`, green tag `NAMES NOBODY`
- Has citations → 1px `#DEEAE3`, white, grey tag `CITED`
- Contract-docs divisions (Div 00) → grey tag, `opacity: 0.75`

Note that green here marks **opportunity**, not confirmation. That is consistent across the
design: green is always "you can still act on this."

Detail line lists the actual section numbers, which is what a rep searches for.

### Specification

Only meaningful when documents exist. Three parts:

**a. The governing rule banner** (`#EDF5F0`, 1px `#2F9E5C`, radius 12px) — if the project's
General Conditions carry a blanket substitution clause, it goes at the top, because it
governs every row beneath it. Maine's reads:

> General Conditions 17.1, p. 36: "the term 'or approved equal' shall be implied, if it is
> not included in the text." Every named product on this project is substitutable with
> written approval by the Consultant. Nothing here is locked.

This is a better pitch than any individual citation and it was not surfaced anywhere in the
production page. Parse for it on every record.

**b. Collapsible legend**, "How to read a position", collapsed by default. It was originally
below the list; with 20 citations that put it out of reach. Six badges:

| Badge | Tone | Meaning |
|---|---|---|
| Open to equals | green | Section names alternates and says "or approved equal" outright |
| Acceptable manufacturer | green | One of several on a named list, list explicitly not closed |
| Basis of design | grey | Product the section was drawn around |
| Named | grey | Manufacturer appears in the section |
| Approved vendor | grey | A source to buy through, not the manufacturer of record |
| Fabricator | amber | Named to fabricate the assembly — hardest to displace, the award is to a shop |

`Locked` and `Performance spec` are real positions in the model that do not occur on this
record. Do not render a badge the document does not support.

**c. Citation rows.** Filter chips above (all / substitution stated / basis of design / by
division), then rows at `padding: 17px 0` with `border-top: 1px solid #DEEAE3`:

- Manufacturer name 16px/600 + position badge
- Product line 14px
- Division and CSI section, 13px `#5B6A79`
- Pull-quote of the actual substitution language where present: italic, `border-left: 2px solid #2F9E5C`, 12px padding
- Right-aligned page cite in monospace 12px

**Every row must carry a page number.** A citation without one cannot ship.

**Empty state** (dashed `#C3D8CB` border, `#F6FAF7`): headline "No specification document has
been published for this project", a paragraph explaining this is a discovered project rather
than a bid record and that a manufacturer cannot be named without a document behind it, two
CTAs (Alert me if a spec publishes / See the scope instead), then **"What you can act on
today"** — three cards pulling the real leverage out of the record. For Hyundai-SK: the
architect is known, the subs are known, the scope is declared.

That last block is what stops a zero-document record from feeling like a dead end.

### Team
Rows: role label (`flex: 0 0 190px`, 11.5px/700/uppercase), name + detail, right-aligned tag.
The spec author gets the green tag; everyone else grey. Unknown participants stay as rows
reading "Not announced" in `#5B6A79` — absence is signal, do not hide the row.

### Documents
Full-card links: title + optional page-count pill, detail line, "Open document →" right-aligned.
Hover: border `#2F9E5C`, background `#F6FAF7`.

Empty state explains the record came from search-grounded discovery rather than a bid portal,
and points at the activity feed for sources. Both states carry the sourcing note.

---

## 3. Right rail

**Ask about this project** (`#EDF5F0`, 1px `#2F9E5C`) — input + Ask button, answer text below,
and a scope line stating which sources answers may draw from. Answers cite held sources only.

**Workspace & activity feed** — All / AI Signals / News segmented filter, then entries with
source, date, title, optional detail. Tag every entry so the filter works. An empty filter
shows a dashed one-liner, not a blank stack.

**Contacts** — org label, name, monospace contact link. Takes 2 or 4 entries.

**Trust note** — "A finding cannot exist in SpecIndex without a source behind it."

---

## Data model

```
record {
  slug, internalId, title, sector, status, statusVariant
  location { city, county, state }
  sourcePulledAt, pageUpdatedAt
  priorityScore { value|null, signal, factors[] }     // null renders "--" / "Not pulled"
  read { headline, stats[3], footer }
  facts[]            { label, value|null }            // null → "Not stated in the source record"
  brief { paragraphs[], attribution }
  scope[]            { code, name, detail, sections[], citationCount, source }
  specRule           { text, cite } | null            // blanket substitution clause
  citations[]        { manufacturer, product, division, csiSection,
                       position, quote|null, document, page }   // page REQUIRED
  documents[]        { title, pageCount|null, detail, url, fetchedAt }
  team[]             { role, name|null, detail, tag, isSpecAuthor }
  contacts[]         { org, name, email|null }
  feed[]             { source, date|null, title, detail, kind: signal|news }
}
```

Derived, never stored: `hasDocuments = documents.length > 0`,
`hasSpec = citations.length > 0`, tab counts, uncited-first scope sort.

---

## Design tokens

**Colors** (locked palette, do not extend)

| Token | Hex | Use |
|---|---|---|
| Green | `#2F9E5C` | Accent, eyebrows, key numbers, open/opportunity borders |
| Forest | `#166534` | Buttons, dark read panel, links, wordmark "Index" |
| Amber | `#F59E0B` | **Rare.** Bidding status pill and the Fabricator badge only |
| Amber tint | `#FDF0D6` | Amber pill fill |
| Ink | `#0C1524` | Body, headings |
| Muted | `#5B6A79` | Secondary text |
| Faint | `#8A9AA8` | Null values, zero stats, low-signal scores |
| On-forest | `#D2E7DB` | Body on forest |
| Muted light | `#A6BBAF` | Secondary on forest |
| Chip | `#E4F2EA` | Light green chip fill |
| Panel | `#EDF5F0` | Tinted card fill |
| Line | `#DEEAE3` | All hairlines |
| Dashed | `#C3D8CB` | Empty-state and placeholder borders |
| Page bg | `#F6FAF7` | |

**Typography**
- Display / headings / numbers: **Space Grotesk** 500/600/700 (Google Fonts), matches the wordmark
- Body / UI: Helvetica Neue, Helvetica, Arial
- Data (IDs, dates, page cites, source meta): `SFMono-Regular, Menlo, monospace`

| Role | Size | Weight | Tracking |
|---|---|---|---|
| H1 | 35 | 700 | -1.1 |
| Read headline | 21 | 600 | -0.4 |
| Score | 31 | 700 | -1.4 |
| Stat number | 27 | 700 | -1 |
| Tab / card title | 15.5–16 | 600–700 | -0.2 |
| Brief body | 16 | 400 | — (line-height 1.7) |
| Body | 14–14.5 | 400 | — (1.55) |
| Card body | 13–13.5 | 400 | — (1.5) |
| Eyebrow | 11 | 700 | 1.6–2.2, uppercase |
| Badge | 10.5 | 700 | 1, uppercase |
| Mono meta | 11–12.5 | 400 | — |

**Radius**: 5–6 chips · 8–9 buttons · 10–12 inner cards · 14 read panel · 16 sections · 999 pills
**Spacing**: 4px base. Section gap 16, column gap 26, page padding 32.
**Shadows**: none anywhere. Hairlines and tint only.

---

## Behavior

- Sticky header at top 0; sticky rail at top 86px.
- Hover: links `#166534` → `#2F9E5C`; primary buttons bg `#166534` → `#2F9E5C`; secondary
  border `#DEEAE3` → `#2F9E5C` with text → `#166534`; document cards border → `#2F9E5C`,
  bg → `#F6FAF7`.
- Transitions: add 120ms ease on color and border-color. Nothing that moves layout.
- **Render server-side.** The current page is client-rendered, which is why `curl` and every
  crawler sees an empty shell. These records are meant to be permanently citable and
  indexable. This is the single highest-value fix in the package.
- Responsive via flex-wrap and auto-fit only. Check 900 / 1200 / 1440.
- All interactive labels need `white-space: nowrap` — pill and badge text must not wrap out
  of its border-radius on a font fallback.

## Copy rules (non-negotiable)

1. **No em dashes or en dashes.** Comma, full stop, parentheses, or the `·` middot already in use.
2. **Never state an inference as a fact.** Position badges come from the document's own words.
3. **Every fact carries a source.** No page cite, no row.
4. **Public-source framing is affirmative**: "100% public-source, every record cited." Never
   defensive language about scraping or plan rooms.
5. **Empty is explained, never blank.** Every zero state says what is missing, why, and what
   to do instead.
6. Evergreen marketing numbers only (`500K+` projects, `50` states, `100%` public-source).
   Record-specific numbers are exact, because they are attached to a cited record.

---

## Findings from the source document — fix these in the pipeline

These came out of reading `reference/3820_Specifications_DOC_MSP.pdf` directly and comparing
it to what production shows. They are extraction bugs, not design issues, but they change
what the page should say.

**1. Recall gap: 20 manufacturer citations exist, production shows 7.**
Missing: Carlisle SynTec (EPDM roofing, ~8 pages, pp. 151–158), Owens Corning FOAMULAR F-400
(pp. 131–132), Sherwin-Williams (pp. 178–183), Corian/DuPont (pp. 197–200), Spacesaver
(p. 188), Bilco (p. 165), PPG (p. 183), GAF, Johns Manville, Elevate/Firestone (all p. 139),
Summit and LG appliances (pp. 192–193), Cotterman (p. 84), APC/Chatsworth/Middle Atlantic
(p. 207). Roughly two thirds of the named manufacturers are being dropped.

**2. The blanket substitution clause is not being parsed.**
General Conditions 17.1, p. 36. It determines the position of all 20 citations and is the
strongest single line on the record. Parse §17 Substitutions on every project manual.

**3. Divisions naming nobody are not surfaced.**
Div 22 Plumbing, Div 23 HVAC and Div 26 Electrical contain zero manufacturers across 219
pages. Div 26 alone runs eleven sections including panelboards, interior lighting, lighting
controls and electricity metering. For an electrical or mechanical rep this absence is the
entire product, and today it is invisible.

**4. Date discrepancy.** Bids were due 1:30pm on **22 June 2026** per the Notice to
Contractors (p. 5). Production and the demo script say 29 June. Verify which is right —
an addendum may have moved it, in which case the record should show the change, not just the
final date.

**5. Same field, two answers.** On the Hyundai-SK page the facts grid says square footage is
not stated while the executive brief gives 3.3M sq ft. Extracted brief values are not writing
back to the structured fields. A customer will spot this immediately.

Also available and unused: substantial completion 15 March 2027 and final completion
31 March 2027 (p. 5), manual dated 28 May 2026, and full CSI section numbers for all 16
divisions from the table of contents (pp. 2–4).

---

## Files

- `Project Record Template v3.dc.html` — the design reference. Open in a browser; use the
  Compare toggle at the top left to flip between records. **Build against this one.**
- `examples/Maine State Prison Gatehouse.dc.html` — the deep record on its own, no toggle.
  What the page looks like with a 219 page spec book behind it.
- `examples/Hyundai-SK Battery Bartow.dc.html` — the shallow record on its own, no toggle.
  What the same template looks like with zero documents.
- `examples/support.js` — runtime for the two example files. Keep it beside them or they
  will not render.
- `reference/3820_Specifications_DOC_MSP.pdf` — the real 219 page project manual. Every Maine
  citation in the design cites into this file and can be verified against it.

The two example files are the same component with the record preset and the prototype-only
Compare toggle removed. Open them side by side in two windows: anything that differs between
them is data, and anything that differs structurally is a bug.

## Verify before calling it done

- Both records render from one component with no record-specific branches beyond data shape.
- A record with zero documents shows written empty states everywhere, never a blank card.
- Server-rendered: `curl` the URL and confirm title, divisions and citations are in the HTML.
- Every citation row has a page number.
- Scope sorts uncited divisions first.
- Reads correctly at 900 / 1200 / 1440.
- No em dashes in any rendered string, including pipeline output.
- No badge or pill text wraps outside its pill.
