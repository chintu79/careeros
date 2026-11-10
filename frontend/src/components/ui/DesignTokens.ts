/**
 * CareerOS Design Tokens
 * Premium dark-first developer workspace tokens: subtle surface depth, editorial typography,
 * precise 4px spacing, restrained emerald accent, and accessible focus rings.
 */

export const TOKENS = {
  colors: {
    canvas: 'var(--color-paper)',
    surface: 'var(--color-paper-2)',
    elevated: 'var(--color-paper-3)',
    overlay: 'var(--color-paper-4)',
    card: 'var(--color-paper-2)',
    cardHover: 'var(--color-hover)',
    sidebar: 'var(--color-sidebar)',
    border: 'var(--color-rule-2)',
    borderMuted: 'var(--color-rule-subtle)',
    borderActive: 'var(--color-rule)',
    accent: 'var(--color-accent)',
    accentBg: 'var(--color-accent-bg)',
    accentBorder: 'var(--color-accent-border)',
    text: {
      primary: 'var(--color-ink)',
      secondary: 'var(--color-ink-2)',
      muted: 'var(--color-muted)',
      disabled: 'var(--color-disabled)',
    },
    semantic: {
      success: 'var(--color-success)',
      warning: 'var(--color-warn)',
      error: 'var(--color-error)',
      info: 'var(--color-info)',
    },
  },

  typography: {
    pageTitle: 'page-title',
    sectionTitle: 'section-title',
    headingLg: 'font-display text-[15px] font-semibold tracking-[-0.015em] text-[var(--color-ink)]',
    headingMd: 'font-display text-[13px] font-semibold tracking-[-0.01em] text-[var(--color-ink)]',
    headingSm: 'text-[12px] font-medium text-[var(--color-ink-2)]',
    subheading: 'text-[13px] text-[var(--color-muted)] font-normal leading-relaxed',
    label: 'field-label',
    body: 'text-[13px] text-[var(--color-ink-2)] leading-relaxed',
    bodyMuted: 'text-[12px] text-[var(--color-muted)] leading-normal',
    mono: 'font-mono text-[12px] tnum',
  },

  spacing: {
    '3xs': '2px',
    '2xs': '4px',
    xs: '8px',
    sm: '12px',
    md: '16px',
    lg: '24px',
    xl: '32px',
    '2xl': '40px',
    '3xl': '48px',
    '4xl': '64px',
  },

  transitions: {
    default: 'transition-colors duration-150 ease-out',
    fast: 'transition-colors duration-100 ease-out',
    transform: 'transition-all duration-150 ease-out',
  },

  radius: {
    xs: 'rounded-[var(--radius-xs)]',
    sm: 'rounded-[var(--radius-sm)]',
    md: 'rounded-[var(--radius-standard)]',
    lg: 'rounded-[var(--radius-card)]',
    xl: 'rounded-[var(--radius-panel)]',
    full: 'rounded-[var(--radius-pill)]',
  },

  shadows: {
    card: 'var(--shadow-card)',
    dropdown: 'var(--shadow-dropdown)',
    modal: 'var(--shadow-modal)',
  },

  focusRing: 'focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]',
};

