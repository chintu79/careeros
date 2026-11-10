/**
 * Accessibility Focus Trap Utility
 * Ensures keyboard navigation stays constrained inside active modals,
 * dialogs, and slide-over drawers per WCAG 2.4.3 (Focus Order).
 */

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'textarea:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(', ');

export function getFocusableElements(container: HTMLElement): HTMLElement[] {
  const elements = Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
  );
  return elements.filter(
    (el) => !el.hasAttribute('disabled') && el.offsetParent !== null
  );
}

export function trapFocus(container: HTMLElement, e: KeyboardEvent | React.KeyboardEvent): void {
  if (e.key !== 'Tab') return;

  const focusables = getFocusableElements(container);
  if (focusables.length === 0) {
    e.preventDefault();
    return;
  }

  const firstElement = focusables[0];
  const lastElement = focusables[focusables.length - 1];

  if (e.shiftKey) {
    // Shift + Tab moving backwards
    if (document.activeElement === firstElement || !container.contains(document.activeElement)) {
      e.preventDefault();
      lastElement.focus();
    }
  } else {
    // Tab moving forwards
    if (document.activeElement === lastElement || !container.contains(document.activeElement)) {
      e.preventDefault();
      firstElement.focus();
    }
  }
}

let previouslyFocusedElement: HTMLElement | null = null;

export function saveActiveElement(): void {
  if (typeof document !== 'undefined' && document.activeElement instanceof HTMLElement) {
    previouslyFocusedElement = document.activeElement;
  }
}

export function restoreActiveElement(): void {
  if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === 'function') {
    // Delay slightly to prevent race conditions during modal unmount
    setTimeout(() => {
      try {
        previouslyFocusedElement?.focus();
      } catch (err) {
        // Element may have been removed from DOM
      }
      previouslyFocusedElement = null;
    }, 50);
  }
}

export function focusFirstElement(container: HTMLElement): void {
  setTimeout(() => {
    const focusables = getFocusableElements(container);
    if (focusables.length > 0) {
      focusables[0].focus();
    } else {
      container.focus();
    }
  }, 50);
}
