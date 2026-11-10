# Design: CareerOS

The locked system. Every Hallmark run reads this first and pages share it. Change it on purpose; the file is the rule.

## System
- Genre: modern-minimal (app screens)
- Shape of the first page: app screen (application workspace)
- Theme: Blueprint (deal 2/3)
- Axes: mid/geometric-sans/neutral · posture: drenched

## Tokens
`tokens.css` is the source of truth. The roles:
```css
:root {
  --color-paper: oklch(35% 0.105 256);  --color-paper-2: oklch(31% 0.10 257);  --color-paper-3: oklch(26.5% 0.095 258);
  --color-ink: oklch(97% 0.012 240);  --color-ink-2: oklch(90% 0.025 242);  --color-muted: oklch(80% 0.045 244);
  --color-rule: oklch(93% 0.02 240 / 0.85);  --color-rule-2: oklch(93% 0.02 240 / 0.32);
  --color-grid: oklch(97% 0.01 240 / 0.09);  --color-grid-2: oklch(97% 0.01 240 / 0.2);
  --color-accent: oklch(97% 0.012 240);  --color-accent-ink: oklch(33% 0.105 256);  --color-focus: oklch(97% 0.012 240);
  --font-display: "Chakra Petch", ui-sans-serif, sans-serif;  --font-body: "IBM Plex Sans", ui-sans-serif, sans-serif;  --font-outlier: "IBM Plex Mono", ui-monospace, monospace;
  --radius-card: 0;  --radius-pill: 0;  --rule-hair: 1px;  --rule-heavy: 2px;  --shadow-card: none;
}
```
The spacing scale, the type scale, the easings and the durations are the scaffold's and live in `tokens.css`.

## Controls
- Primary: ink fill (`--color-ink`), `--color-accent-ink` text, square (0 radius), 44px full height, 32-40px app controls with a 44px hit target.
- Secondary: 1px outlined (`--color-rule`), same radius and height.
- Focus: 2px `--color-focus` ring, never a glow.
- Labelface: IBM Plex Sans 500 sentence case a step smaller, untracked; mono only for measurements.

## Motion
- Character: still; one drafted rule may draw itself once a page.
- Under prefers-reduced-motion everything ends at once.

## Registers (app screens)
- Figures as dimension strings; tables as drawing registers keylined with a `--rule-heavy` head rule; forms as title blocks; timings/stage numbers in mono column.
- The signature: application registers (the drawing-set of the job search).
- One page max per register pattern; tables before cards; 32-40px controls.

## Exports
`tokens.css` in this project. Tailwind, DTCG or shadcn blocks are added here on request, per `export-formats.md`.
