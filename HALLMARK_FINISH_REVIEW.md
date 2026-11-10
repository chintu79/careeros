# Hallmark Finish Review — CareerOS Blueprint Redesign

**Date**: 2026-11-07  
**App**: http://localhost:5174/  
**System**: Blueprint (prussian-blue sheet, one white-line signal, Chakra Petch 600 display, IBM Plex Sans body, IBM Plex Mono numerals; zero radius; keylined surfaces; no hue; no shadows)  
**Gates**: 0 FAIL, 0 REFLEX, build/tsc pass, no console errors, no H-overflow 320-1920px, 9 pages Playwright-verified

---

## Findings (max 12, ranked P0/P1/P2)

1. **P1 — Display headlines at weight 500 not 600 (systematic, all 9 pages)**  
   Every H2/H3 uses Chakra Petch `font-medium` (500) instead of required `font-semibold` (600). Affected: sidebar section labels ("Workspace", "Intelligence", "Personal" at text-[10px]), page titles ("Overview", "Applications" at text-[13px]), card headlines on ai-assistant. Fix: change `font-medium` → `font-semibold` on all display-role headings.

2. **P1 — Sidebar nav section labels lack display weight**  
   H3 elements with class `mb-1.5 px-5 text-[10px] font-medium leading-[1.6] text-[var(--color-muted)]` render at 500 weight. These are register headers per design.md ("figures as dimension strings; tables as drawing registers"). Fix: `font-medium` → `font-semibold`.

3. **P1 — Page title H2 lacks display weight**  
   H2 with class `truncate text-[13px] font-medium text-[var(--color-ink-2)]` renders at 500 weight. This is the primary page register title. Fix: `font-medium` → `font-semibold`.

4. **P1 — AI Assistant card headlines lack display weight**  
   H3 elements with class `mt-1 text-[13px] font-medium leading-snug text-[var(--color-ink)]` (deadline cards, action cards) render at 500 weight. Fix: `font-medium` → `font-semibold`.

5. **P2 — Keyboard shortcut KBDs use mono for non-measurements**  
   KBD elements (⌘K, ⌘J, ?, K) use IBM Plex Mono but design.md restricts mono to "measurements". Keyboard shortcuts are a reasonable exception; flag for consistency review. Fix: either allow mono for shortcuts in design.md or use body font with distinct styling.

6. **P2 — Overview page content contrast unverified**  
   Page was in loading state ("Loading your command center…") during capture; dashboard widgets, stat cards, and empty states not contrast-checked. Fix: verify 4.5:1 on all text once data loads.

7. **P2 — Mobile (390px) sidebar/icon-only nav density**  
   .taste-skill/after screenshots show icon-only rail at 390px; verify tap targets ≥44px and no clipped labels. Fix: spot-check 390px across all 9 pages.

8. **P2 — Skip link focus state uses emerald-500 not token focus**  
   Skip-to-content link uses `focus:bg-emerald-500 focus:text-slate-950 focus:shadow-2xl focus:rounded-lg` — emerald hue leak and shadow violate "no hue; no shadows". Fix: use `--color-focus` ring, token bg, zero radius.

9. **P2 — Focus ring offset on skip link uses slate-950 not paper**  
   `focus:ring-offset-slate-950` should be `--color-paper-3` for consistency. Fix: replace with token.

10. **P2 — Button min-heights inconsistent (30px vs 32px vs 44px)**  
    Header buttons: `min-h-[30px]`, `min-h-[32px]`; design.md specifies "44px full height, 32-40px app controls with 44px hit target". Fix: unify to 44px hit target, 32-40px visual.

11. **P2 — KBD border uses --color-rule-2 (0.32 opacity) not --color-rule (0.85)**  
    Keyboard shortcut chrome uses lighter rule weight than other keylines. Fix: use `--color-rule` for consistency or document intent.

12. **P2 — SR-only H1 "CareerOS , Overview" uses Chakra Petch 400**  
    Screen-reader page title uses display font at weight 400. Fix: `font-semibold` or move to body font since not visually rendered.

---

## What was not checked / risks

- **Overview dashboard content contrast** — page stuck in loading state; stat cards, charts, empty states unverified for 4.5:1.
- **Mobile 320/375px across all 9 pages** — only 390px sampled in .taste-skill/after; 320/375 may reveal clipped text or broken layouts.
- **Dynamic states** — modals, toasts, dropdowns, loading skeletons, error states not captured in static screenshots.
- **Animation/motion** — "one drafted rule may draw once" rule not verified; prefers-reduced-motion behavior untested.
- **Print stylesheet** — not reviewed.