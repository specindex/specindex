# SpecIndex Design System

**Implementation:** `lib/design-tokens.ts` + `app/globals.css`

The visual language is deliberately plain: warm stone backgrounds, Geist for everything, Geist Mono for figures, amber for actions, and forest green for stats and labels.

Any front-end change should check this file first for an existing token/pattern before inventing a new one -- especially color, spacing, and type-scale decisions. If a change needs something not listed here, add it here in the same PR rather than leaving the doc stale.

---

## Typography

| Role | Family | Notes |
|---|---|---|
| UI / headings / body | **Geist** | 400 body, 500 buttons, 700 h1/h2 |
| Data / stats / mock UI | **Geist Mono** | County grids, timestamps, metrics, IDs |

Loaded via the `geist` npm package (Vercel's own font, shipped as `next/font/local` under the hood -- not on Google Fonts) in `app/layout.tsx`, exposed as `--font-geist-sans` / `--font-geist-mono`. Switched from Inter/JetBrains Mono/Space Grotesk 2026-08-07 -- see "Font history" below.

### Font history

Previously Inter (body/UI) + JetBrains Mono (data) site-wide, with Space
Grotesk added 2026-08-07 for the project record page redesign only. Same day,
replaced with the single Geist system above, site-wide -- a second opinion
(Gemini, multimodal review of the redesigned project record page) flagged
Space Grotesk's "quirky ink-trap" character as working against the
enterprise-trust tone this product needs, and recommended Geist + Geist Mono
as the modern standard for data-dense B2B software (the same system Vercel
and Linear use). Adopted for the whole site, not just the one page, so
there's one typographic voice rather than three.

### Scale

| Token | Size | Weight |
|---|---|---|
| Hero (`text-hero`) | clamp(2.25rem → 3rem) | 700, tracking -0.02em |
| Section (`text-section`) | clamp(1.75rem → 2.25rem) | 700 |
| Body | 16px / 1.625 line-height | 400 |
| Eyebrow (`text-eyebrow`) | 12px uppercase | 600, green, tracking 0.1em |
| Stat (`text-stat`) | clamp(2rem → 2.75rem) | 700, green |

---

## Colors

| Token | Hex | Usage |
|---|---|---|
| `--color-bg` | `#FAFAF9` | Page background (stone-50) |
| `--color-ink` | `#1A1A1A` | Primary text |
| `--color-white` | `#FFFFFF` | Cards, header |
| `--color-amber` | `#F59E0B` | Primary CTA buttons |
| `--color-amber-hover` | `#D97706` | CTA hover |
| `--color-green` | `#166534` | Eyebrows, stats, links, logo mark, Request Demo button |
| `--color-green-hover` | `#14532D` | Request Demo hover |
| `--color-green-light` | `#DCFCE7` | Pills, active county cells |
| `--color-gray-600` | `#57534E` | Body secondary |
| `--color-gray-400` | `#A8A29E` | Captions, labels |
| `--color-border` | `#E7E5E4` | Borders, dividers |

---

## Components

### Buttons
- **Primary:** amber bg, ink text, 8px radius
- **Demo:** green bg (logo mark green), white text -- header + homepage hero
  "Request Demo" only, pilot before rolling out to other pages' Request Demo
  CTAs (docs/PROJECT_PAGE_REDESIGN.md's Hyundai-first rollout pattern)
- **Outline:** white/transparent, border, hover gray-100

### Cards
- White bg, 1px border, subtle shadow
- **Elevated:** larger shadow for product mock

### Layout patterns
1. Sticky white header — logo mark + nav + amber CTA
2. Hero — eyebrow + headline + subcopy + CTA, product mock right
3. **Live stats band** — dark green (`#0F4A25`, one shade darker than `--color-green`) full-bleed section, light-green (`#A7F3C8`) status pill + label, 2×2 (or 4-up on wide) `font-mono tabular-nums` stat tiles in bordered white/5-alpha cards. Real data only — never a placeholder/skeleton bar. Sits directly after the hero, ahead of prose sections, so trust signals land before persuasion copy (added 2026-07-30, homepage redesign).
4. Stats strip — 4-up green numbers on white (legacy variant of #3; keep the dark band for homepage, this one is fine for lighter-weight pages)
5. Problem statement — centered prose
6. Feature sections — "Out of the Box" label + split content/mock
7. **3-step accordion** — numbered (`01`/`02`/`03`) `<details>` elements, only step one `open` by default, used for genuinely sequential processes only (e.g. discovery → enrichment → delivery). Don't reach for this shape unless the content is actually an ordered sequence. (added 2026-07-30)
8. 3-step process (static, non-collapsing variant — prefer the accordion above when steps have real supporting detail)
9. Comparison rows (Others / SpecIndex)
10. **Mid-page CTA band** — solid `--color-green`, centered white h2 + one line of support copy + white pill button. Use once per page, positioned as a pacing break before the final CTA — not adjacent to another CTA. (added 2026-07-30)
11. FAQ accordion
12. Demo form + footer columns

---

## Pages

| Route | Purpose |
|---|---|
| `/` | Marketing home |
| `/product/` | Use cases |
| `/how-it-works/` | 4-step workflow |
| `/pricing/` | Free / Pro / Team tiers |
| `/about/` | Company story |
| `/projects/` | Georgia project search (product) |
| `/visibility/` | Brand visibility tool (product) |
| `/projects/[id]/` | Project detail |

---

## Project record page

**Route:** `/project/[id]/` (moved from `/projects/[id]/` 2026-08-07 -- see
"Routing" below). **Implementation:** `components/ProjectDetailView.tsx` +
`components/project-detail/*`. **Source spec:** `docs/handoff_project_record_template 2/`.

This page uses its OWN token set (`--sx-*` custom properties in
`app/globals.css`), deliberately not reusing the site's `--color-*` tokens,
so this palette can't leak into marketing pages and vice versa. Fonts are
shared with the rest of the site (`--font-sans` / `--font-mono` /
`--font-display`, all Geist -- see Typography above).

### Colors (`--sx-*`)

| Token | Hex | Usage |
|---|---|---|
| `--sx-green` | `#2F9E5C` | Accent, eyebrows, key numbers, open/opportunity borders |
| `--sx-forest` | `#166534` | Buttons, dark "read" panel, links |
| `--sx-amber` | `#F59E0B` | Rare -- bidding status pill only |
| `--sx-amber-tint` | `#FDF0D6` | Amber pill fill |
| `--sx-ink` | `#0C1524` | Body, headings |
| `--sx-muted` | `#5B6A79` | Secondary text |
| `--sx-faint` | `#8A9AA8` | Null values, zero stats, low-signal scores |
| `--sx-on-forest` | `#D2E7DB` | Body text on the dark forest panel |
| `--sx-muted-light` | `#A6BBAF` | Secondary text on forest |
| `--sx-chip` | `#E4F2EA` | Light green chip fill |
| `--sx-panel` | `#EDF5F0` | Tinted card fill |
| `--sx-line` | `#DEEAE3` | All hairlines |
| `--sx-dashed` | `#C3D8CB` | Empty-state / placeholder / null-value borders |
| `--sx-page-bg` | `#F6FAF7` | Page background |

### Type scale

| Role | Size | Weight | Tracking |
|---|---|---|---|
| H1 | 35px | 700 | -1.1px |
| Read panel headline | 21px | 600 | -0.4px |
| Score number | 31px | 700 | -1.4px |
| Stat tile number | 27px | 700 | -1px |
| Tab / card title | 15.5-16px | 600-700 | -0.2px |
| Body | 14-16px | 400 | -- |
| Eyebrow | 10.5-11px | 700 | 1.3-2.2px, uppercase |
| Mono meta (IDs, dates, page cites) | 11-12.5px | 400 | -- |

### Key patterns

- **The "read" panel inverts** on whether the record has documents/citations:
  dark forest (`--sx-forest`) with white text when it does, light
  (`--sx-page-bg`) with ink text when it doesn't. A record with nothing
  cited never gets the dark "authoritative" treatment -- visual weight tracks
  substance, or every record reads equally credible regardless of evidence.
- **Zero-value stat tiles that only duplicate the facts grid below them are
  hidden entirely**, not shown as three "0" cards (fixed 2026-08-07 -- see
  Gemini review below).
- **A null/unpulled score (`--/100`) gets a dashed border, transparent
  background** -- never the same solid elevated card treatment as a real
  score, or a non-existent metric visually outranks a real one.
- **Uppercase source-data strings (owner/architect/GC/project titles) are
  title-cased display-side** via `toDisplayCase()` in `lib/format.ts` --
  preserves acronyms (LLC, PLLC, SK) via an explicit allowlist rather than
  naively lowercasing everything. Never applied to citation quotes -- those
  must render exactly as the source document has them.
- **Facts grid uses `flex-wrap`, not CSS `grid`.** An earlier version used
  `display: grid` with a colored container background showing through 1px
  gaps as hairlines -- with a variable fact count and `auto-fit` columns,
  an incomplete last row left grid tracks reserved-but-empty, which either
  the container background (solid slab) or neighboring cells' own
  box-shadow hairlines (hollow outlined box) turned into a visible,
  unintentional shape. `flex-wrap` doesn't reserve space beyond actual
  content, so an incomplete row just ends with nothing to render. Any other
  "gap-as-hairline" grid on the site should use this pattern, not
  `display: grid`.
- Never render an empty fact as a blank/muted cell -- omit it entirely
  (`Fact` returns `null`) or replace it with a written absence
  (`AbsentFactCell`, e.g. "Unassigned, pre-award"), matching the site-wide
  "state the absence and why" rule already established for the corpus data
  model (see `lib/format.ts`'s `EMPTY_FACT_VALUES`).

### Design review log

Two-way AI design reviews (Gemini, multimodal) ran 2026-08-07 against
screenshots of the live page. Findings applied: hidden zero-stat read
tiles, de-emphasized null-score card, display-side uppercase formatting,
monospace applied to dates, Space Grotesk replaced with Geist site-wide (see
Font history above). Findings intentionally NOT applied (judged low-impact
or already-adequate on a second pass): right-rail dead space on sparse
records, floating trust-note restyling, WCAG contrast tweak on the "THE
READ" eyebrow tag.

### Routing

Individual project pages live at `/project/[id]/` (singular), not
`/projects/[id]/`. They can't share a route depth with the pSEO hub pages at
`/projects/[state]/[trade]/` -- Next.js's router rejects two different
dynamic segment names (`id` vs `state`) at the same URL depth. Old
`/projects/{id}/` links 301-redirect to `/project/{id}/` via `firebase.json`.

---

## Do / Don't

**Do:** Geist everywhere, amber CTAs, green stats/eyebrows, stone page bg, white sections  
**Don't:** Foundation gold/black hero, Montserrat/Proxima, purple gradients, dark blueprint grids, Space Grotesk (retired 2026-08-07)
