import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { Brand } from './Brand';
import { LINKS } from './content';

const PRODUCT_LINKS = [
  { label: 'Product', href: '#product' },
  { label: 'Features', href: '#features' },
  { label: 'Open source', href: '#open-source' },
  { label: 'Documentation', href: LINKS.docs, external: true },
  { label: 'GitHub', href: LINKS.repository, external: true },
];

export const LandingNav = () => {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
        toggleRef.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <header className="l-nav">
      <a className="l-skip" href="#main">
        Skip to content
      </a>
      <div className="l-container l-nav__inner">
        <a className="l-nav__brand" href="/welcome" aria-label="CareerOS home">
          <Brand />
        </a>

        <nav className="l-nav__links" aria-label="Primary">
          {PRODUCT_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="l-nav__link"
              {...(link.external ? { target: '_blank', rel: 'noreferrer' } : {})}
            >
              {link.label}
              {link.external ? <ArrowUpRight size={12} aria-hidden="true" /> : null}
            </a>
          ))}
        </nav>

        <div className="l-nav__actions">
          <a className="l-button l-button--primary l-button--small" href="/">
            Get started
          </a>
          <button
            ref={toggleRef}
            type="button"
            className="l-nav__toggle"
            aria-expanded={open}
            aria-controls="landing-mobile-nav"
            aria-label={open ? 'Close menu' : 'Open menu'}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          </button>
        </div>
      </div>

      {open ? (
        <nav id="landing-mobile-nav" className="l-nav__mobile" aria-label="Mobile">
          {PRODUCT_LINKS.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="l-nav__mobile-link"
              onClick={() => setOpen(false)}
              {...(link.external ? { target: '_blank', rel: 'noreferrer' } : {})}
            >
              {link.label}
              {link.external ? <ArrowUpRight size={14} aria-hidden="true" /> : null}
            </a>
          ))}
          <a className="l-button l-button--primary l-nav__mobile-cta" href="/">
            Get started
          </a>
        </nav>
      ) : null}
    </header>
  );
};
