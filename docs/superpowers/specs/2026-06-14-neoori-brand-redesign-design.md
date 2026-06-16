# neoori — Brand Redesign (design only)

**Date:** 2026-06-14
**Scope:** Visual identity only. **Zero functionality changes** — no data flow, API calls, routes, form logic, auth, payments, or copy semantics altered. Colors, typography, layout, spacing, component styling, placement, and structure are all in scope.

## Goal
Give neoori a single coherent high-end identity across every screen, derived from the official brand kit and the v1.7 deliverable PDF. Replace the legacy "warm-paper terracotta" placeholder theme.

## Brand foundation (from official kit)
- **Orange** `#ea5624` — primary. CTAs, active states, links, the infinity mark, accents, focus rings.
- **Peach** `#f7ae78` — secondary soft. Highlight/"Signal" callouts, hover tints, gradient partner.
- **Navy** `#1c3561` — institutional anchor. Headers, section bands, structure, body-ink derivative.
- **White / warm-neutral** — crisp surfaces. Drops the cream `#faf7f0` era.
- **Tagline:** "Unlock Your Potential. Shape Your Tomorrow" — used as a quiet brand signature.

## Color tokens (CSS, `globals.css`)
shadcn reads `--background/--foreground/--primary/...`; editing `:root` reskins ~70% of the app automatically. Brand raw tokens exposed as Tailwind utilities via `@theme inline` (`bg-navy`, `text-navy`, `bg-peach`, `bg-peach-soft`, `text-orange`, `bg-paper`).

| token | value | role |
|---|---|---|
| `--background` | `#ffffff` | page |
| `--foreground` | `#16233c` | deep-navy body ink |
| `--card` | `#ffffff` | cards |
| `--primary` | `#ea5624` | orange |
| `--primary-foreground` | `#ffffff` | |
| `--secondary` / `--muted` / `--accent` | `#f4f2ee` warm-light | light fills (stays light!) |
| `--muted-foreground` | `rgba(22,35,60,.58)` | secondary text |
| `--border` | `rgba(22,35,60,.12)` | navy-tint hairlines |
| `--ring` | `#ea5624` | orange focus |
| `--radius` | `0.75rem` | rounder, premium |
| brand: `--color-navy #1c3561`, `--color-navy-ink #16233c`, `--color-orange #ea5624`, `--color-orange-dark #cf4a1c`, `--color-peach #f7ae78`, `--color-peach-soft #fdecdc`, `--color-paper #f8f7f4`, `--color-success #1f8a5b` |

`--secondary` MUST stay light — many surfaces use `bg-secondary` as a light fill. Navy is its own token, never `--secondary`.

## Typography
Loaded via `next/font/google` (variable) in `layout.tsx`, exposed as `--font-display / --font-sans / --font-mono`.
- **Plus Jakarta Sans** → `--font-display`: `h1,h2`, big numbers, wordmark, section titles. `letter-spacing:-0.02em`.
- **Inter** → `--font-sans`: body (default).
- **JetBrains Mono** → `--font-mono`: eyebrows (uppercase tracked), `§N`, data labels, dates, codes.
Base layer auto-applies display font to `h1,h2`.

## Logo — `components/brand/Logo.tsx`
Recreated in code (swap for client vector later via 1 line). Wordmark = `ne` + **infinity mark** (two overlapping stroked rings = the "oo") + `ri`, in display font.
- Props: `variant?: 'full' | 'mark'`, `tone?: 'navy' | 'light'`, `className`, `animate?`.
- Mark: two overlapping ring `<circle>`s, orange→peach `linearGradient`. `tone='light'` → wordmark white (for navy/dark backgrounds).
- `animate` → stroke-draw via `stroke-dashoffset` keyframe (hero only), reduced-motion safe.
- `app/icon.svg` = the mark → favicon.

## Component language
- **Cards:** white, `rounded-xl`, ring `navy/10`, soft shadow, `.hover-lift` (translateY-2 + shadow) on interactive cards.
- **Buttons:** primary = orange solid/white; secondary = navy solid/white; outline = navy-tint border; ghost. Hover darkens via `--color-orange-dark`.
- **Eyebrows:** mono, uppercase, `tracking-widest`, orange.
- **`§N` chips:** orange square, white mono number (unifies app report with PDF; replaces ink circular badges).
- **Callouts:** peach-soft bg + orange left bar ("Signal à lever"); navy info bands.
- **Inputs:** clean, orange focus ring.
- **Chips/toggles (mobilité):** selected = orange; idle = navy-tint border, peach hover.

## Motion (tasteful micro)
`globals.css` keyframes + `@media (prefers-reduced-motion: reduce)` kill-switch. infinity stroke-draw (hero), fade/slide-up on hero blocks, hover lifts, 150–250ms eases, soft orange→peach gradients. No scroll libraries.

## Report screen → align to PDF v1.7 (`analyse/[id]/rapport`, `c/[token]`)
Bring on-screen report to the deliverable's look: orange top rule → **navy header band** (orange "neoori", white name, orange italic cible line, contact) → orange `§N` chip + navy title band per section → peach "Signal" callouts → force cards w/ orange left bar + orange "Pour la cible" italic → navy "ACTION N" tags → §3 tag-cloud grid → footer rule. Print CSS preserved + color-exact (`print-color-adjust`).

## Surfaces (all design-only)
landing · `Header` · `AppBar` · auth (connexion/inscription) · form (`nouveau`, `orientation`) · dashboard (`espace`) · report (`rapport`) · counselor (`c/[token]`) · paywall (`debloquer`) · en-cours (loading) · admin (layout + 6 pages) · legal (3) · skeletons · `icon.svg` · metadata.

## Constraints
- Next 16 (not stock — `next/font` verified against local docs). Tailwind v4 CSS-config (no `tailwind.config`). `@base-ui/react` primitives.
- Don't touch: handlers, fetches, schemas, routes, `lib/*`, `types`, backend. French UI copy preserved (tone rules in CLAUDE.md respected).
- Build must pass (`next build`); print/PDF output must stay intact.

## Execution
1. Foundation by hand (coherence): `globals.css`, `layout.tsx`, `Logo.tsx`, `icon.svg`, primitives (button/badge/card/input/alert), `Header`/`AppBar`.
2. Flagship surfaces by hand: landing, report, form, dashboard, auth, paywall, counselor.
3. Fan-out (ultracode Workflow): secondary surfaces (admin, legal, en-cours) mechanical token/pattern application + exhaustive hardcoded-color audit + adversarial design-QA review.
4. Verify build green; visual QA; report to user; commit/push only on user request (note: `initial` is the live deploy branch).
