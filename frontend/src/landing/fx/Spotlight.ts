import type { PointerEvent } from 'react';

// One delegated listener per demo writes the pointer position into CSS vars;
// the overlay itself lives in chapters.css. No state, no re-render.
export const trackSpotlight = (event: PointerEvent<HTMLElement>) => {
  const element = event.currentTarget;
  const rect = element.getBoundingClientRect();
  element.style.setProperty('--spot-x', `${event.clientX - rect.left}px`);
  element.style.setProperty('--spot-y', `${event.clientY - rect.top}px`);
};
