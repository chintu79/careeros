import { Fragment, useEffect } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Container,
  GitPullRequest,
  Scale,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import { LandingNav } from './LandingNav';
import { ProductFrame } from './ProductFrame';
import { Reveal } from './Reveal';
import { FeatureVisual } from './FeatureVisuals';
import { Walkthrough } from './Walkthrough';
import { Terminal } from './Terminal';
import { Brand } from './Brand';
import {
  CREDIBILITY,
  FAQ,
  FEATURES,
  HERO_WORDS,
  LINKS,
  STACK,
} from './content';
import './landing.css';

const CREDIBILITY_ICONS = [Scale, Container, GitPullRequest, ShieldCheck];

// lucide-react no longer ships brand marks; keep the GitHub glyph inline.
const GitHubMark = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2.17c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.12 3.05.74.8 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.68.8.56A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
  </svg>
);

const LandingPage = () => {
  useEffect(() => {
    const previousTitle = document.title;
    const meta = document.querySelector('meta[name="description"]');
    const previousDescription = meta?.getAttribute('content') ?? '';
    document.title = 'CareerOS: your career deserves a command center';
    meta?.setAttribute(
      'content',
      'CareerOS is an open-source, self-hostable career intelligence workspace: opportunity discovery, application tracking, resume generation and interview preparation.',
    );
    document.documentElement.dataset.page = 'landing';
    return () => {
      document.title = previousTitle;
      meta?.setAttribute('content', previousDescription);
      delete document.documentElement.dataset.page;
    };
  }, []);

  return (
    <div className="landing">
      <LandingNav />

      <main id="main">
        <section className="l-hero" aria-labelledby="hero-title">
          <div className="l-hero__glow" aria-hidden="true" />
          <div className="l-container l-hero__grid">
            <div className="l-hero__copy">
              <h1 id="hero-title" className="l-hero__title">
                {HERO_WORDS.map((word, index) => (
                  <Fragment key={`${word}-${index}`}>
                    {index > 0 ? ' ' : null}
                    <span
                      className="l-hero__word"
                      style={{ ['--word-index' as string]: index }}
                    >
                      {word}
                    </span>
                  </Fragment>
                ))}
              </h1>
              <p className="l-hero__lead">
                Discover opportunities, track applications, build better resumes, and manage
                your career from one open-source workspace.
              </p>
              <div className="l-hero__actions">
                <a className="l-button l-button--primary" href="#product">
                  Explore CareerOS
                  <ArrowRight size={16} aria-hidden="true" />
                </a>
                <a
                  className="l-button l-button--secondary"
                  href={LINKS.repository}
                  target="_blank"
                  rel="noreferrer"
                >
                  <GitHubMark />
                  View on GitHub
                </a>
              </div>
              <ul className="l-hero__facts">
                <li>Apache-2.0</li>
                <li>Self-hosted</li>
                <li>No paid services required</li>
              </ul>
            </div>

            <div className="l-hero__visual">
              <ProductFrame />
            </div>
          </div>
        </section>

        <section className="l-proof" aria-label="Project facts">
          <div className="l-container l-proof__grid">
            {CREDIBILITY.map((item, index) => {
              const Icon = CREDIBILITY_ICONS[index];
              return (
                <a
                  key={item.title}
                  className="l-proof__item"
                  href={item.href}
                  target="_blank"
                  rel="noreferrer"
                >
                  <span className="l-proof__icon" aria-hidden="true">
                    <Icon size={17} strokeWidth={1.7} />
                  </span>
                  <span className="l-proof__copy">
                    <span className="l-proof__title">{item.title}</span>
                    <span className="l-proof__body">{item.body}</span>
                  </span>
                  <ArrowUpRight size={14} className="l-proof__arrow" aria-hidden="true" />
                </a>
              );
            })}
          </div>
        </section>

        <section id="features" className="l-section" aria-labelledby="features-title">
          <div className="l-container">
            <Reveal className="l-section__head">
              <h2 id="features-title" className="l-h2">
                The whole search, in one workspace.
              </h2>
              <p className="l-lead">
                Discovery, tracking, resumes and interview prep share the same data. A role
                moves through the system once, and every view stays current.
              </p>
            </Reveal>

            <div className="bento">
              {FEATURES.map((feature) => (
                <article
                  key={feature.id}
                  className={`bento-card bento-card--${feature.span}`}
                >
                  <div className="bento-card__copy">
                    <h3 className="bento-card__title">{feature.title}</h3>
                    <p className="bento-card__body">{feature.body}</p>
                  </div>
                  <div className="bento-card__visual">
                    <FeatureVisual visual={feature.visual} />
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="product" className="l-section l-section--product" aria-labelledby="product-title">
          <div className="l-container">
            <Reveal className="l-section__head">
              <h2 id="product-title" className="l-h2">
                From first search to signed offer.
              </h2>
              <p className="l-lead">
                Three stages, one record. Preview the workflow without creating an account or
                touching a database.
              </p>
            </Reveal>
            <Walkthrough />
          </div>
        </section>

        <section id="open-source" className="l-section l-section--open" aria-labelledby="open-title">
          <div className="l-container l-open">
            <Reveal className="l-open__copy">
              <h2 id="open-title" className="l-h2">
                Open source, end to end.
              </h2>
              <p className="l-lead">
                The backend, frontend, deployment files and tests are in the same repository
                under Apache-2.0. There is no open-core gate and no hosted tier to upgrade to.
              </p>
              <ul className="l-check-list">
                <li>Run the full stack with Docker Compose</li>
                <li>Bring your own PostgreSQL, or use the bundled one</li>
                <li>Keep AI optional: Groq or local Ollama</li>
                <li>Read every migration, test and security note before you run it</li>
              </ul>
              <div className="l-open__links">
                <a className="l-text-link" href={LINKS.license} target="_blank" rel="noreferrer">
                  Read the license <ArrowUpRight size={14} aria-hidden="true" />
                </a>
                <a className="l-text-link" href={LINKS.contributing} target="_blank" rel="noreferrer">
                  Contributing guide <ArrowUpRight size={14} aria-hidden="true" />
                </a>
              </div>
            </Reveal>

            <div className="l-open__terminal">
              <Terminal />
              <p className="l-note">
                Backups are operator-run. The bundled scripts write unencrypted snapshots with
                SHA-256 checksums, which verify integrity, not confidentiality.
              </p>
            </div>
          </div>
        </section>

        <section id="stack" className="l-section" aria-labelledby="stack-title">
          <div className="l-container">
            <Reveal className="l-section__head">
              <h2 id="stack-title" className="l-h2">
                A stack you can inspect.
              </h2>
              <p className="l-lead">
                No proprietary runtime and no hidden service. These are the versions and
                components the repository ships.
              </p>
            </Reveal>
            <dl className="l-stack">
              {STACK.map((row) => (
                <div className="l-stack__row" key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section id="faq" className="l-section" aria-labelledby="faq-title">
          <div className="l-container l-faq">
            <Reveal className="l-faq__head">
              <h2 id="faq-title" className="l-h2">
                Questions worth asking.
              </h2>
              <p className="l-lead">
                Straight answers about licensing, hosting, data and AI. If something is not
                ready, it is not claimed here.
              </p>
            </Reveal>
            <div className="l-faq__list">
              {FAQ.map((item) => (
                <details className="l-faq__item" key={item.question}>
                  <summary className="l-faq__question">
                    <span>{item.question}</span>
                    <span className="l-faq__plus" aria-hidden="true" />
                  </summary>
                  <p className="l-faq__answer">{item.answer}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="l-close" aria-labelledby="close-title">
          <div className="l-container l-close__inner">
            <div className="l-close__copy">
              <h2 id="close-title" className="l-close__title">
                Put your career in one place.
              </h2>
              <p className="l-close__lead">
                Open the workspace, or run the whole stack yourself. No account, no trial and
                no hosted dependency.
              </p>
            </div>
            <div className="l-close__actions">
              <a className="l-button l-button--primary" href="/">
                <Sparkles size={16} aria-hidden="true" />
                Get started
              </a>
              <a
                className="l-button l-button--secondary"
                href={LINKS.docs}
                target="_blank"
                rel="noreferrer"
              >
                Read the docs
                <ArrowUpRight size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        </section>
      </main>

      <footer className="l-footer">
        <div className="l-container l-footer__grid">
          <div className="l-footer__brand">
            <a href="/welcome" aria-label="CareerOS home">
              <Brand />
            </a>
            <p>
              Open-source career intelligence. Self-hosted, single-tenant and built to be
              inspected.
            </p>
          </div>
          <nav className="l-footer__col" aria-label="Product">
            <h2 className="l-footer__heading">Product</h2>
            <a href="#features">Features</a>
            <a href="#product">Walkthrough</a>
            <a href="#faq">FAQ</a>
          </nav>
          <nav className="l-footer__col" aria-label="Resources">
            <h2 className="l-footer__heading">Resources</h2>
            <a href={LINKS.docs} target="_blank" rel="noreferrer">
              Documentation
            </a>
            <a href={LINKS.readme} target="_blank" rel="noreferrer">
              Readme
            </a>
            <a href={LINKS.license} target="_blank" rel="noreferrer">
              License
            </a>
          </nav>
          <nav className="l-footer__col" aria-label="Project">
            <h2 className="l-footer__heading">Project</h2>
            <a href={LINKS.repository} target="_blank" rel="noreferrer">
              GitHub
            </a>
            <a href={LINKS.ci} target="_blank" rel="noreferrer">
              CI workflow
            </a>
            <a href={LINKS.security} target="_blank" rel="noreferrer">
              Security
            </a>
            <a href={LINKS.contributing} target="_blank" rel="noreferrer">
              Contributing
            </a>
          </nav>
        </div>
        <div className="l-container l-footer__bottom">
          <span>Apache-2.0</span>
          <span>© 2026 CareerOS</span>
          <span>React, FastAPI, PostgreSQL</span>
        </div>
      </footer>
    </div>
  );
};

export default LandingPage;
