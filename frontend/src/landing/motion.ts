import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export { gsap, ScrollTrigger };

/**
 * Wire a chapter's scroll scene inside a gsap context. The context owns every
 * timeline and ScrollTrigger the setup creates, and ctx.revert() removes them
 * on unmount. Reduced motion never builds a scene: callers must render their
 * final state statically.
 */
export function withScrollScene(
  scope: Element | null,
  setup: () => void,
): () => void {
  if (!scope || prefersReducedMotion() || typeof window === 'undefined') {
    return () => {};
  }
  const ctx = gsap.context(setup, scope);
  return () => ctx.revert();
}
