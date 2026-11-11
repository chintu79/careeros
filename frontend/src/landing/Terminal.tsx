import { useState } from 'react';
import { Check, Copy, Terminal as TerminalIcon } from 'lucide-react';
import { INSTALL_COMMANDS } from './content';

type CopyState = 'idle' | 'copied' | 'failed';

export const Terminal = () => {
  const [state, setState] = useState<CopyState>('idle');

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
    <div className="terminal">
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
