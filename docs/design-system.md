# SpecIndex Design System

**Implementation:** `lib/design-tokens.ts` + `app/globals.css`

The visual language is deliberately plain: warm stone backgrounds, Inter for everything, JetBrains Mono for figures, amber for actions, and forest green for stats and labels.

---

## Typography

| Role | Family | Notes |
|---|---|---|
| UI / headings / body | **Inter** | 400 body, 500 buttons, 700 h1/h2 |
| Data / stats / mock UI | **JetBrains Mono** | County grids, timestamps, metrics |

Loaded via `next/font/google` in `app/layout.tsx`.

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

## Do / Don't

**Do:** Inter everywhere, amber CTAs, green stats/eyebrows, stone page bg, white sections  
**Don't:** Foundation gold/black hero, Montserrat/Proxima, purple gradients, dark blueprint grids
