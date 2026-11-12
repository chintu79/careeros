import { useEffect, useRef } from 'react';
import { ArrowUpRight, ShieldCheck } from 'lucide-react';
import { LINKS } from './content';
import { Terminal } from './Terminal';
import { gsap, withScrollScene } from './motion';

export const OpenSourceChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.l-open__copy > *', {
          opacity: 0,
          y: 18,
          duration: 0.45,
          stagger: 0.07,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 72%' },
        });
        gsap.from('.l-open__terminal', {
          opacity: 0,
          y: 22,
          duration: 0.55,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 68%' },
        });
      }),
    [],
  );

  return (
    <section
      id="open-source"
      ref={scope}
      className="l-chapter l-chapter--alt"
      aria-labelledby="open-source-title"
    >
      <div className="l-container l-open l-chapter__grid">
        <div className="l-open__copy">
          <h2 id="open-source-title" className="l-h2">
            Your career workspace. Your infrastructure. Your rules.
          </h2>
          <p className="l-lead">
            The complete stack ships under Apache-2.0: backend, frontend, deployment files and tests.
            There is no open-core gate, no hosted tier and no vendor who can raise your price.
          </p>
          <ul className="l-check-list">
            <li>Tested with disposable Compose runs; CI on every pull request</li>
            <li>Single-tenant by design; do not expose it as a multi-user service</li>
            <li>Backups are operator-run: unencrypted snapshots, SHA-256 for integrity, not secrecy</li>
            <li>AI is optional; deterministic paths work with no provider configured</li>
            <li>No managed hosting, no PITR, no encryption you did not configure yourself</li>
          </ul>
          <div className="l-open__links">
            <a className="l-text-link" href={LINKS.license} target="_blank" rel="noreferrer">
              Read the license <ArrowUpRight size={14} aria-hidden="true" />
            </a>
            <a className="l-text-link" href={LINKS.security} target="_blank" rel="noreferrer">
              Security policy <ArrowUpRight size={14} aria-hidden="true" />
            </a>
            <a className="l-text-link" href={LINKS.contributing} target="_blank" rel="noreferrer">
              Contributing guide <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </div>
        </div>

        <div className="l-open__terminal">
          <div className="l-star">
            <Terminal animate />
          </div>
          <p className="l-note">
            <ShieldCheck size={13} aria-hidden="true" />
            Verify every line before you run it. The commands above are the ones the repository
            documents for a first install.
          </p>
        </div>
      </div>
    </section>
  );
};
