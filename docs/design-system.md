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
| `--color-green` | `#166534` | Eyebrows, stats, links, logo mark |
| `--color-green-light` | `#DCFCE7` | Pills, active county cells |
| `--color-gray-600` | `#57534E` | Body secondary |
| `--color-gray-400` | `#A8A29E` | Captions, labels |
| `--color-border` | `#E7E5E4` | Borders, dividers |

---

## Components

### Buttons
- **Primary:** amber bg, ink text, 8px radius
- **Outline:** white/transparent, border, hover gray-100

### Cards
- White bg, 1px border, subtle shadow
- **Elevated:** larger shadow for product mock

### Layout patterns
1. Sticky white header — logo mark + nav + amber CTA
2. Hero — eyebrow + headline + subcopy + CTA, product mock right
3. Stats strip — 4-up green numbers on white
4. Problem statement — centered prose
5. Feature sections — "Out of the Box" label + split content/mock
6. 3-step process
7. Comparison rows (Others / SpecIndex)
8. FAQ accordion
9. Demo form + footer columns

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
