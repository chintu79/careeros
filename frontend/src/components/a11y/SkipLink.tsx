import React from 'react';

interface SkipLinkProps {
  targetId?: string;
  label?: string;
}

// Hallmark · Blueprint: focus ring is the white line; no hue, no shadow, zero radius.
export const SkipLink: React.FC<SkipLinkProps> = ({
  targetId = 'main-content',
  label = 'Skip to main content',
}) => {
  return (
    <a
      href={`#${targetId}`}
      className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[100] focus:border focus:border-[var(--color-rule)] focus:bg-[var(--color-ink)] focus:px-4 focus:py-2 focus:text-[13px] focus:font-semibold focus:text-[var(--color-accent-ink)] focus:outline-none focus:ring-2 focus:ring-[var(--color-focus)] focus:ring-offset-0 focus:ring-offset-[var(--color-paper-3)]"
    >
      {label}
    </a>
  );
};
