import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { AlertTriangle, ArrowLeft } from 'lucide-react';

interface UnsavedChangesContextValue {
  setGuard: (id: string, message: string | null) => void;
  requestNavigation: (apply: () => void) => void;
}

const UnsavedChangesContext = createContext<UnsavedChangesContextValue | null>(null);

/**
 * Returns a navigate(apply) function that either applies immediately (no dirty
 * editors mounted) or opens the shared confirmation dialog.
 */
export function useNavigationGuard(): (apply: () => void) => void {
  const ctx = useContext(UnsavedChangesContext);
  return useCallback((apply: () => void) => {
    if (ctx) ctx.requestNavigation(apply);
    else apply();
  }, [ctx]);
}

/**
 * Registers an editor as holding unsaved changes while `isDirty` is true.
 * A successful save must flip the flag to false; unmounting clears it too.
 */
export function useUnsavedChangesGuard(id: string, isDirty: boolean, message: string): void {
  const ctx = useContext(UnsavedChangesContext);
  const setGuard = ctx?.setGuard;
  useEffect(() => {
    if (!setGuard) return;
    setGuard(id, isDirty ? message : null);
    return () => setGuard(id, null);
  }, [setGuard, id, isDirty, message]);
}

interface UnsavedChangesProviderProps {
  children: React.ReactNode;
}

export function UnsavedChangesProvider({ children }: UnsavedChangesProviderProps): React.ReactElement {
  const [guards, setGuards] = useState<Record<string, string>>({});
  const guardsRef = useRef(guards);
  guardsRef.current = guards;
  const [pending, setPending] = useState<(() => void) | null>(null);
  const stayButtonRef = useRef<HTMLButtonElement>(null);

  const setGuard = useCallback((id: string, message: string | null) => {
    setGuards(prev => {
      if (message === null) {
        if (!(id in prev)) return prev;
        const next = { ...prev };
        delete next[id];
        return next;
      }
      if (prev[id] === message) return prev;
      return { ...prev, [id]: message };
    });
  }, []);

  // If navigation was blocked and every dirty editor is now saved, release it.
  useEffect(() => {
    if (pending && Object.keys(guardsRef.current).length === 0) {
      const fn = pending;
      setPending(null);
      fn();
    }
  }, [guards, pending]);

  // One permanent beforeunload handler that reads the live guard registry.
  // (Removing the listener at unmount depends on a state flush that may not
  // run once the root is torn down, which hangs jsdom teardown.)
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (Object.keys(guardsRef.current).length === 0) return;
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, []);

  // Focus the primary safe action whenever the dialog opens.
  useEffect(() => {
    if (pending) stayButtonRef.current?.focus();
  }, [pending]);

  const stay = useCallback(() => setPending(null), []);

  // Minimal focus trap between the two footer actions; Escape = stay.
  const handleDialogKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      stay();
      return;
    }
    if (e.key !== 'Tab') return;
    const focusables = e.currentTarget.querySelectorAll<HTMLButtonElement>('button');
    if (focusables.length < 2) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (e.shiftKey) {
      if (active === first || !e.currentTarget.contains(active)) {
        e.preventDefault();
        last.focus();
      }
    } else if (active === last || !e.currentTarget.contains(active)) {
      e.preventDefault();
      first.focus();
    }
  }, [stay]);

  const requestNavigation = useCallback((apply: () => void) => {
    if (Object.keys(guardsRef.current).length === 0) {
      apply();
      return;
    }
    // Replace any previous pending request; never stack dialogs.
    setPending(() => apply);
  }, []);

  const discardAndLeave = useCallback(() => {
    setGuards({});
    setPending(prev => {
      prev?.();
      return null;
    });
  }, []);

  const dirtyEntries = Object.entries(guards);
  const summary = dirtyEntries.length > 1
    ? `${dirtyEntries.length} editors hold unsaved changes`
    : dirtyEntries[0]?.[1] ?? 'Changes that are not saved will be lost';

  const contextValue = useMemo(() => ({ setGuard, requestNavigation }), [setGuard, requestNavigation]);

  return (
    <UnsavedChangesContext.Provider value={contextValue}>
      {children}
      {pending && (
        <div
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="unsaved-changes-title"
          aria-describedby="unsaved-changes-body"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-[2px]"
          onClick={(e) => { if (e.target === e.currentTarget) stay(); }}
          onKeyDown={handleDialogKeyDown}
        >
          <div className="w-full max-w-sm rounded-[var(--radius-card)] border border-[var(--color-rule)] bg-[var(--color-paper-2)] p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-amber-400/25 bg-amber-400/[0.06]">
                <AlertTriangle className="h-4 w-4 text-amber-300" aria-hidden="true" />
              </span>
              <div className="min-w-0">
                <h2 id="unsaved-changes-title" className="text-[14px] font-semibold text-[var(--color-ink)]">
                  Discard unsaved changes?
                </h2>
                <p id="unsaved-changes-body" className="mt-1.5 text-[12.5px] leading-relaxed text-[var(--color-ink-2)]">
                  {summary}. Leaving this page discards everything that was not explicitly saved.
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
              <button
                type="button"
                ref={stayButtonRef}
                onClick={stay}
                className="inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-white/[0.10] px-3.5 text-[12px] font-medium text-[var(--color-ink)] transition-colors hover:bg-white/[0.05] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Stay and keep editing</span>
              </button>
              <button
                type="button"
                onClick={discardAndLeave}
                className="inline-flex min-h-[36px] items-center justify-center rounded-[var(--radius-control)] border border-rose-400/30 bg-rose-400/[0.08] px-3.5 text-[12px] font-medium text-rose-300 transition-colors hover:bg-rose-400/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/60"
              >
                <span>Discard changes and leave</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </UnsavedChangesContext.Provider>
  );
}
