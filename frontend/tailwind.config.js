/** @type {import('tailwindcss').Config} */
// CareerOS v2 — dark-first, one accent (#65E6C2), Geist Sans + Geist Mono.
// Defact the same token names so components keep working.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          50: '#F3F6F8', 100: '#E9EDF0', 200: '#C9D2DA', 300: '#A0ABB8',
          400: '#7B8794', 500: '#717E8D', 600: '#4E5A68', 700: '#2A333D',
          800: '#1C2631', 850: '#171F28', 900: '#121820', 950: '#0B0E12',
        },
        dark: {
          950: '#0B0E12', 900: '#121820', 850: '#121820', 800: '#171F28',
          750: '#171F28', 700: '#252F3A', 600: '#2A333D', 500: '#717E8D',
          400: '#A0ABB8', 300: '#A0ABB8', 200: '#F3F6F8', 100: '#F3F6F8',
        },
        slate: {
          50: '#F3F6F8', 100: '#F3F6F8', 200: '#E9EDF0', 300: '#A0ABB8',
          400: '#A0ABB8', 500: '#717E8D', 600: '#717E8D', 700: '#252F3A',
          800: '#252F3A', 850: '#171F28', 900: '#121820', 950: '#0B0E12',
        },
        brand: {
          50: 'rgba(101, 230, 194, 0.08)', 100: 'rgba(101, 230, 194, 0.14)',
          400: '#65E6C2', 500: '#65E6C2', 600: '#4FD5B0', 700: '#3A9478',
        },
        emerald: { 300: '#7FE5C0', 400: '#65E6C2', 500: '#4FD5B0', 600: '#35A882', 700: '#2A9470', 800: '#1C5A46', 900: '#121F1A', 950: '#0E1613' },
        green: { 300: '#7FE5C0', 400: '#65E6C2', 500: '#4FD5B0', 600: '#35A882', 800: '#1C5A46', 900: '#121F1A', 950: '#0E1613' },
        teal: { 300: '#7FE5C0', 400: '#65E6C2', 500: '#4FD5B0', 800: '#1C5A46', 900: '#121F1A', 950: '#0E1613' },
        sky: { 300: '#8FBBE8', 400: '#7AA7E0', 500: '#5C8CC1', 800: '#15233E', 900: '#0E1626', 950: '#0A0F1A' },
        amber: { 300: '#E5C878', 400: '#DDB75A', 500: '#C9A03F', 800: '#332A14', 900: '#1F1A0E', 950: '#141009' },
        rose: { 300: '#D98A8A', 400: '#D97F7F', 500: '#BF6262', 800: '#331E1E', 900: '#1F1414', 950: '#140C0C' },
        blue: { 300: '#8FBBE8', 400: '#7AA7E0', 500: '#5C8CC1', 600: '#4FD5B0', 800: '#15233E', 900: '#0E1626', 950: '#0A0F1A' },
        neutral: { 50: '#F3F6F8', 100: '#E9EDF0', 200: '#C9D2DA', 300: '#A0ABB8', 400: '#717E8D', 500: '#717E8D', 600: '#4E5A68', 700: '#2A333D', 800: '#1C2631', 900: '#171F28', 950: '#0B0E12' },
      },
      fontFamily: {
        sans: ['"Geist Sans"', 'Geist', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        display: ['"Geist Sans"', 'Geist', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        xs: ['0.75rem', { lineHeight: '1.1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.2rem' }],
        base: ['0.875rem', { lineHeight: '1.4rem' }],
      },
      borderRadius: {
        none: '0',
        sm: '6px',
        md: '8px',
        DEFAULT: '8px',
        lg: '8px',
        xl: '12px',
        '2xl': '16px',
        full: '999px',
      },
      animation: {
        'fade-in': 'fadeIn 150ms cubic-bezier(0.16, 1, 0.3, 1)',
        'zoom-in': 'zoomIn 180ms cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slideDown 160ms cubic-bezier(0.16, 1, 0.3, 1)',
        'shimmer': 'shimmer 1500ms infinite linear',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        zoomIn: { '0%': { opacity: '0', transform: 'scale(0.98)' }, '100%': { opacity: '1', transform: 'scale(1)' } },
        slideDown: { '0%': { opacity: '0', transform: 'translateY(-4px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
    },
  },
  plugins: [],
}
