import { useEffect, useRef, useState } from 'react';
import { Check, Copy, Terminal as TerminalIcon } from 'lucide-react';
import { INSTALL_COMMANDS } from './content';

type CopyState = 'idle' | 'copied' | 'failed';

export const Terminal = ({ animate = false }: { animate?: boolean }) => {
  const [state, setState] = useState<CopyState>('idle');
  const [visible, setVisible] = useState(!animate);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!animate) return;
    const node = rootRef.current;
    if (!node || typeof IntersectionObserver !== 'function') {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '0px 0px -20% 0px', threshold: 0.35 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [animate]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(INSTALL_COMMANDS);
      setState('copied');
      window.setTimeout(() => setState('idle'), 2200);
    } catch {
      setState('failed');
    }
  };

  return (
    <div className={`terminal${visible ? ' is-running' : ''}`} ref={rootRef}>
      <div className="terminal__bar">
        <span className="terminal__label">
          <TerminalIcon size={14} aria-hidden="true" />
          Self-host install
        </span>
        <button type="button" className="terminal__copy" onClick={copy}>
          {state === 'copied' ? <Check size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
          {state === 'copied' ? 'Copied' : 'Copy commands'}
        </button>
      </div>
      <pre className="terminal__body" tabIndex={0} aria-label="Self-host installation commands">
        <code>
          {INSTALL_COMMANDS.split('\n').map((line, index) => (
            <span
              key={`${line}-${index}`}
              style={{ ['--line-index' as string]: index }}
              className={`terminal__line${line.startsWith('#') ? ' terminal__line--comment' : ''}`}
            >
              {line || ' '}
            </span>
          ))}
        </code>
      </pre>
      <p className="terminal__status" role="status" aria-live="polite">
        {state === 'failed' ? 'Clipboard unavailable. Select the commands and copy them manually.' : ''}
      </p>
    </div>
  );
};
