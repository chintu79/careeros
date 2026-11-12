# CareerOS `/welcome` — redesign design

Date: 2026-11-12 · Branch: `feat/landing-page` · Status: direction approved (teal); committed on approval of the brief
Research receipts: `/home/krishna/Desktop/interniq/refs/` (screenshots + metrics) · Before screenshots: `/home/krishna/Desktop/interniq/before-1920-*.png`

## Intent and why

The landing page promises “a product with a distinct visual identity and a deliberate design philosophy”. It currently reads as a competent template: components are handsome, but nothing decides itself. This redesign applies one idea — **one record, from first search to signed offer** — with the discipline of the references and the identity of the actual app, without copying anyone.

Non-goals: no backend changes, no release-branch changes, no push/merge/deploy, no invented features or claims, no new runtime dependencies, no touching `release-3.1.0`, `main`, or PR #2.

## Phase 1 — reference research (condensed)

Measured 1440×900 (+390×844 mobile); screenshots for visual pass. **Motion and eased choreography could not be verified from stills; every motion claim below is marked unverified unless noted.** Footers were not visible in most stills (unverified).

| Category | Notion | Linear | Stripe | Framer | Raycast | Vercel | Webflow |
|---|---|---|---|---|---|---|---|
| Visual identity | white field, near-black text, blue primary, editorial sans + serif accents (Lyon), high contrast | near-black #08090A, white type, slate subtext, Inter Variable 510 | white field, purple primary, blue/orange/pink gradient ribbon, sohne thin 300 | near-black, white type, blue glow inside product mock, GT Walsheim 500 | black, broad diagonal red beams, white type, Inter 600, Instrument Serif display fallback in font set | monochrome black-on-white, Geist, weight 400 display, -3.8px tracking | off-white, black type, blue accent + announcement banner, WF Visual Sans |
| Layout | full-bleed nav, centred max-w containers; hero 3-up capability cards; section rhythm 96px-ish | 1333–1425px container; sections ~128px top/bottom; feature grids 3–4 cols | 1230–1275px containers; ~2200–4500px tall stacked sections | 1200–1425px containers; 100–120px section pads | centred single-column hero; 2–3 col cards below | sticky 64px nav; 12-col grid, ~1377px container | blue banner over nav; centred container; stat-card grids |
| Hero | left-aligned giant (~96px/600, -4.6px) with one accent pill; two CTAs; screenshot below fold | left-aligned ~64px/510, stacked 6 lines; subhead one line; full-bleed black, no bg image | 48px thin headline, accent phrase in purple; gradient ribbon, no UI; logo wall | 54px start-aligned; headline + 2 CTAs + browser-frame canvas mock, panel fills fold | centred ~64px/600, one sentence subhead, single “Download” pill, fine print | “Agentic Infrastructure” 64px/400, triangle mark; black primary + outline secondary | “Build for what’s next”, blue banner, stat cards below |
| Storytelling | problem → proof → agent ladder (“Where teams and agents ship together” → “AI where your team works”) | product-first: hero → full-screen app screenshot → features (“Intake and integrations” → “Build, review, and ship” → prefooter “Built for the future”) | trust → story → breadth (50% Fortune 100 → Hertz case → product chips) | value → agents → platform (“Start with Agents” → feature grid) | hero → feature cards (AI Chat) | infra thesis → shipped details; metrics strip | hero → stat grid → case cards with photos |
| Motion | unverified (5 animated nodes; 1 video) | unverified (156 animated nodes; heavy) | unverified (3; 2 canvas) | unverified (16; 5 videos) | unverified (28; 1 canvas) | unverified (2; 1 canvas) | unverified (28; 1 canvas, GSAP present) |
| Product visuals | real UI screenshots in grey rounded frames (Ramp HQ) | frameless dark UI, 1px dark borders, chip accents only | photography + gradients, no UI | live canvas-style mock with agent sidebar | bordered dark cards containing real UI panels | almost none in hero; customer-logo wall instead | static customer screenshots; badge walls |
| Navigation | 64px relative nav, 5 links + demo + 2 CTAs | 73px fixed nav, blur(20px); 6 links + 2 pills | 76px relative nav; 6 links + sign-in + “Contact sales” (purple) | 64px nav; dropdowns; “Sign up” pill | top bar + 8 links; “Download” pill; logo left | sticky 64px nav; Products/Resources dropdowns; Get a Demo / Sign Up pills | banner + nav; Contact Sales; “Start for free” pill |
| Footer | unverified (logo wall under hero) | unverified | unverified | unverified | unverified | unverified (customer wall at hero base) | unverified |
| Mobile 390 | hamburger; stacked hero; blue CTA; avatar chips; logo wall scrolls | hamburger keeps logo + auth; headline 5 lines; app panel narrows with left rail | gradient scales behind type; full-width purple CTA; logos crop | hamburger + auth; mock becomes full-width; cookie banner fixed bottom | hamburger only; beams crop; one pill CTA | triangle centred; full-width black CTA; logos crop | hamburger; 3-line stack; stat cards become arrow-carousel |

### Synthesis — what CareerOS should borrow

- **From Linear:** the discipline. Dark field, one full-strength CTA, product UI as the only "image", 1px rules, zero glow on UI, accent only inside chips/buttons. Linear is the proof that dark credibility comes from restraint, not decoration.
- **From Notion:** the editorial frame. Oversized display type with exactly one accented word, a problem → proof ladder, real UI in frames, hero fold = headline + one sentence + actions, everything else below the fold. Its 96px fluid type is too big for our 18ch headings; take the rhythm, not the pixels.
- **From Stripe:** atmosphere, not content. One sweeping gradient surface behind the hero (we have `LaserFlow` + aurora) and a max-is-my-promise container discipline. Ignore the light palette and the logo wall (we may not invent customer proof).
- **From Framer:** treat the product as the demo — interactive sample state over screenshots, kept in 1:1 frames; mirror later (ant: the “agent thinking” right rail), never copied literally. Our Linear-thread demos already do this.
- **From Raycast:** the composed fold. Centred intent is optional; what we adopt is the single primary CTA and micro-metadata in fine type (e.g., “Open-source · Apache-2.0 · single-tenant” under actions) instead of scattered badges.
- **From Vercel:** ruthless grid and equal left/right edges. And the counter-lesson: its monochrome minimalism reads premium only because its brand is the canvas; it is the wrong tier of restraint for a pre-1.0 open-source product.
- **Not borrowed — Webflow:** marketing volume, badge walls, carousels. It is the templates we are rejecting.

**Coherent direction proposed:** *dark editorial* — Instrument Serif display + Geist body + Geist Mono figures, one atmospheric hero surface, product UI as imagery, restrained accent, layered "record" composition. Not a mash-up; one personality: **a ledger for a career — written, measured, self-hosted.**

## Phase 3 — diagnosis of the seven feedback items

1. **Ch01 container not correctly centred.** Measured at 1920: `#problem .l-container` and every other container are geometrically centred (left 333 / right 1573 at 1920; `.container { width:100%; max-width:1240px; margin-inline:auto; padding-inline:48px }` — correct). The *optical* defect is real, though: the absolute fragments are right-heavy (f1 2%L, f3/f4/f5 right 0/2%/16%, f7 left 0, f6 10%L) and two fragments disappear on the right while the left stays empty. Fix = genuinely symmetric orbit with matched vertical rhythm and no hardcoded offsets, plus an optical test at 1920/1440/768/390/320. Rebalance, not transforms.
2. **Ch02 “Connected workspace”.** Fails as designed: `WebThreads` at 0.5 opacity dominates the field (bright arcs across the whole panel), the headline is left-aligned while the composition below is centred, the module cards are six floating boxes with no relationship, and the ProductFrame is undersized. Rethink: replace with a **single thread scene** — one hairline path drawn on scroll, the shared illustrative Linear thread passing through Discover → Track → Resume → Interview → Insights nodes, `ProductFrame` as the settled centre, modules become the path's nodes rather than panels. WebThreads removed (it is wallpaper, not storytelling).
3. **Footer branding.** Current: small lockup (icon + wordmark at 14px), wordmark pill + weak ghost outline text, nav columns all the same grey, maker line timid. Rebuild: real lockup block (mark + “CareerOS” at display scale), 4-column grid on one baseline, licensing row with three facts, clearer hierarchy Product / Resources / Project, ghost wordmark kept only as a masked baseline rule behind the CTA (or deleted), maker line promoted to first-class “Colophon” row. No new claims.
4. **Hero animation not connected to navbar.** Current: words clip-reveal independently of the nav; visual floats in detached. Redesign the sequence as one directed take: nav frames the scene → beam emerges from nav boundary → headline descends from nav line (masked lines, `transform-origin: 50% 0%`) → subhead → CTAs → facts → product frame settles with scale from the nav edge. One ease family, one clock, compositor-friendly transforms, `prefers-reduced-motion` = final state.
5. **Technology stack is a prose table.** Replace with a **strata diagram**: five layers (Presentation — React/Vite/Tailwind; Service — FastAPI/SQLAlchemy; Data — PostgreSQL 17 + pgvector; Integrations — sources + optional GitHub/Calendar + optional Groq/Ollama; Delivery — Docker Compose + nginx + pytest/Vitest/CI). Branded marks only where licence permits (they are prose/inline SVG), small captions, hover states, connected, caption lists actual versions. No invented integrations (Adzuna excluded; Groq/Ollama and calendars marked optional; backups/single-tenant truths kept).
6. **FAQ.** Replace accordion rows with an editorial docs index: sticky left column (“Questions worth asking”, dek, mailto), numbered right column 01–06, two registers (fact / consequence), open-state accent on the number only, `details/summary` semantics retained. No chevron-plus motif, no identical rows, no em-dash-in-prose (Hallmark floor).
7. **Closing CTA redundancy.** Evaluate honestly: `.l-close` and the footer repeat the same job (contain one line, one primary CTA, one link to docs). **Decision: merge.** The footer becomes the ending — CTA band inside the footer grid, then brand/colophon grid, then legal bar. One downward accelerating rhythm, one CTA per screen, no orphan section.

## Layout system (proposed)

- One container: `width:100%; max-width:1240px; margin-inline:auto; padding-inline:clamp(20px,5vw,48px)`. At ≥1728px hero container 1320px only if the art direction wants more air; otherwise stay 1240px for equal edges. No section overrides `max-width` independently (fixes the 1920 drift concern by construction).
- Section spacing: `clamp(88px, 10vw, 128px)` block padding; chapter separators are hairline rules (`--l-rule-soft`), not cards.
- Type scale (desktop): display hero ~96px/92px clamp to 44px mobile; h2 sections 44/40 clamp; lead 18/26; body 14/22; meta 12/18; mono for numerals only. No arbitrary sizes in components.
- Breakpoints: 1024/768/390/320; mobile flattens Ch01 orbit and Ch02 thread only — everything else stacks with the same container.
- Alignment law: every section's inner edge on the shared container; Cta/caption/proof rows align to it too (equal edges, 4).

## Typography candidates

Instrument Serif (display) + Geist (body) + Geist Mono (figures) retained — they continue to fit "ledger". Retained pending direction approval (see Approach B).

## Color and surfaces

Direction **approved: teal alignment**. The app's accent `#65E6C2` replaces the violet across the landing's `--l-violet-*` family (accent, wash, glow, panel, line, mark, underline, CTA/hover fills and the ink used on accent washes). The mint/positive-semantic tokens collapse into the same teal (no second green). Radii, spacing and the 1px border law are unchanged; focus rings instant; hover = 1px border lift + 2px translate; no blur-on-glass outside the hero scene. Notion-style one-accent-word treatment uses teal.

## Motion language

GSAP + ScrollTrigger + Flip only. Hero-from-nav scene; Ch01 scroll-scrubbed orbit peel (kept, rebalanced); Ch02 thread draw + node resolve; chapter entrances stay minimal (one or two elements per section, never a full-page fade); demo micro-interactions stay (`Flip` board, count-up insights, tailored pulse). WebThreads removed. No new WebGL except the existing LaserFlow + Flip. Reduced motion: static end-state everywhere; jsdom/`matchMedia` guards preserved. Mobile: identical sequence, shorter distances, no scrubbed scenes under 1025px.

## Storytelling spine (same shared illustrative Linear thread everywhere)

01 Scattered 02 Connected 03 Discover 04 Track 05 Resume 06 Interviews 07 Insights 08 Open source → Stack ("how it's built") → FAQ ("before you self-host") → Footer w/ integrated CTA. All sample data stays Linear · Backend Engineering Intern · 92, labelled illustrative; Adzuna stays retired; AI optional; no hiring-outcome claims.


## Builder-settled calls (mine, marked on the record)

- Ch02 node labels come from `content.ts` CHAPTERS (Discover, Track, Resume, Interviews, Insights); no new chapters, no new copy claims; the shared thread stays Linear · Backend Engineering Intern · score 92.
- Hero: the nav structure is unchanged (links, CTA placement); only the *origin* of the hero pieces changes. Masked lines use clip-path + translateY with `transform-origin: 50% 0%`, one GSAP timeline, compositor-only.
- Stack strata: textual monochrome names, no invented brand marks; the only inline third-party glyph remains the GitHub octocat. Versions are read from what the repository ships; Groq, Ollama, GitHub and Calendar integrations are labelled optional; Adzuna is not mentioned as a source; backups/single-tenant caveats survive.
- FAQ: the six questions and answers stay verbatim (copy passes, no new claims); chrome changes only.
- Footer merge: the CTA band reuses the existing `/` (workspace) and docs links, GitHub + author credits, legal row (Apache-2.0 · © 2026 CareerOS · stack line). `.l-close` section and its tests go; `l-close__inner` styles removed.
- Tests: `LandingPage.test.tsx` is updated to the merged footer ending (CTA band + wordmark + credits), plus reduced-motion static-state coverage already in place; no snapshot noise.
- Commit strategy: this spec is committed (docs commit) once you approve; the redesign lands as one `feat(landing):` implementation commit (spec + page + tests) unless split at review.
