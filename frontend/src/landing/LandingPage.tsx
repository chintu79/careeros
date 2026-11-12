import { Fragment, useEffect, useRef } from 'react';
import {
  ArrowRight,
  ArrowUpRight,
  Container,
  GitPullRequest,
  Scale,
  ShieldCheck,
} from 'lucide-react';
import { LandingNav } from './LandingNav';
import { ProductFrame } from './ProductFrame';
import { Reveal } from './Reveal';
import { ChapterProgress } from './ChapterProgress';
import { DevAnnotation } from './DevAnnotation';
import { ScatteredChapter } from './ScatteredChapter';
import { ConnectedChapter } from './ConnectedChapter';
import { DiscoverChapter } from './DiscoverChapter';
import { TrackChapter } from './TrackChapter';
import { ResumeChapter } from './ResumeChapter';
import { InterviewChapter } from './InterviewChapter';
import { InsightsChapter } from './InsightsChapter';
import { OpenSourceChapter } from './OpenSourceChapter';
import { Brand } from './Brand';
import { Magnetic } from './fx/Magnetic';
import { LaserFlow } from './fx/LaserFlow';
import { withScrollScene, gsap } from './motion';
import {
  AUTHOR,
  CREDIBILITY,
  FAQ,
  LINKS,
  STACK_LAYERS,
} from './content';
import './landing.css';
import './chapters.css';

const CREDIBILITY_ICONS = [Scale, Container, GitPullRequest, ShieldCheck];

const HERO_LINES = ['Your career', 'deserves a', 'command center.'] as const;

// lucide-react no longer ships brand marks; keep the GitHub glyph inline.
const GitHubMark = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.11.79-.25.79-.56v-2.17c-3.2.7-3.87-1.54-3.87-1.54-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11.1 11.1 0 0 1 5.79 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.12 3.05.74.8 1.18 1.83 1.18 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.68.8.56A10.52 10.52 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z" />
  </svg>
);

const LandingPage = () => {
  const page = useRef<HTMLDivElement | null>(null);
  const heroFrame = useRef<HTMLDivElement | null>(null);

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

  useEffect(
    () =>
      withScrollScene(page.current, () => {
        const stack = page.current?.querySelector('#stack');
        const faq = page.current?.querySelector('#faq');
        const footer = page.current?.querySelector('.l-footer');

        gsap.from('.l-stratum', {
          opacity: 0,
          y: 18,
          duration: 0.45,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: stack, start: 'top 76%' },
        });
        gsap.from('.l-faq__aside > *', {
          opacity: 0,
          y: 16,
          duration: 0.5,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: faq, start: 'top 74%' },
        });
        gsap.from('.l-faq__item', {
          opacity: 0,
          y: 12,
          duration: 0.4,
          stagger: 0.05,
          ease: 'power2.out',
          scrollTrigger: { trigger: faq, start: 'top 70%' },
        });
        gsap.from('.l-footer__cta-copy > *, .l-footer__cta-actions > *', {
          opacity: 0,
          y: 16,
          duration: 0.5,
          stagger: 0.09,
          ease: 'power2.out',
          scrollTrigger: { trigger: '.l-footer__cta', start: 'top 88%' },
        });
        gsap.from('.l-footer__grid > *', {
          opacity: 0,
          y: 16,
          duration: 0.45,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: footer, start: 'top 92%' },
        });
        gsap.from('.l-footer__wordmark', {
          opacity: 0,
          y: 24,
          duration: 0.7,
          ease: 'power2.out',
          scrollTrigger: { trigger: footer, start: 'top 88%' },
        });
      }),
    [],
  );

  return (
    <div className="landing" ref={page}>
      <LandingNav />
      <ChapterProgress />

      <main id="main">
        <section className="l-hero" aria-labelledby="hero-title">
          <div className="l-hero__glow" aria-hidden="true" />
          <div className="l-container l-hero__grid">
            <div className="l-hero__copy">
              <h1 id="hero-title" className="l-hero__title">
                {HERO_LINES.map((line, index) => (
                  <Fragment key={line}>
                    {index > 0 ? ' ' : null}
                    <span className="l-hero__line">
                      <span className="l-hero__line-inner">{line}</span>
                    </span>
                  </Fragment>
                ))}
              </h1>
              <p className="l-hero__lead">
                Discover opportunities, track applications, build better resumes, and manage
                your career from one open-source workspace.
              </p>
              <div className="l-hero__actions">
                <a className="l-button l-button--primary" href="#problem">
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
              <div className="l-hero__stage">
                <LaserFlow
                  className="l-hero__laser"
                  surfaceRef={heroFrame}
                  beamPosition={0.68}
                  color="#65e6c2"
                  intensity={1.25}
                  beamWidth={1.2}
                  flare={1.2}
                  spread={1.2}
                  spill={0.4}
                  fog={0.04}
                  dust={0.9}
                  streaks={1}
                  dots={0.6}
                  pulse={1.1}
                  speed={1}
                  mouseInteraction
                />
                <div className="l-hero__frame" ref={heroFrame}>
                  <ProductFrame />
                </div>
              </div>
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

        <ScatteredChapter />
        <ConnectedChapter />
        <DiscoverChapter />
        <TrackChapter />
        <ResumeChapter />
        <InterviewChapter />
        <InsightsChapter />
        <OpenSourceChapter />

        <section id="stack" className="l-section l-stack" aria-labelledby="stack-title">
          <div className="l-container">
            <Reveal className="l-section__head">
              <h2 id="stack-title" className="l-h2">
                A stack you can inspect.
              </h2>
              <p className="l-lead">
                No proprietary runtime and no hidden service. Five layers, versions the
                repository actually ships.
              </p>
            </Reveal>
            <ol className="l-strata">
              {STACK_LAYERS.map((layer) => (
                <li key={layer.index} className="l-stratum">
                  <span className="l-stratum__index">{layer.index}</span>
                  <div className="l-stratum__body">
                    <span className="l-stratum__name">{layer.name}</span>
                    <ul className="l-stratum__items">
                      {layer.items.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <p className="l-stratum__note">{layer.note}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section id="faq" className="l-section" aria-labelledby="faq-title">
          <div className="l-container l-faq-grid">
            <div className="l-faq__aside">
              <h2 id="faq-title" className="l-h2">
                Questions worth asking.
              </h2>
              <p className="l-lead">
                Answers kept honest to what ships: licensing, hosting, data and AI. If
                something is not ready, it is not claimed here.
              </p>
              <a className="l-text-link l-faq__email" href={`mailto:${AUTHOR.email}`}>
                Something missing? Email the author
                <ArrowUpRight size={14} aria-hidden="true" />
              </a>
            </div>
            <div className="l-faq__list">
              {FAQ.map((item, index) => (
                <details className="l-faq__item" key={item.question}>
                  <summary className="l-faq__question">
                    <span className="l-faq__num" aria-hidden="true">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <span className="l-faq__qtext">{item.question}</span>
                  </summary>
                  <div className="l-faq__answer-wrap">
                    <p className="l-faq__answer">{item.answer}</p>
                  </div>
                </details>
              ))}
            </div>
          </div>
        </section>

      </main>

      <footer className="l-footer">
        <div className="l-container l-footer__cta">
          <div className="l-footer__cta-copy">
            <h2 className="l-footer__cta-title">Put your career in one place.</h2>
            <p className="l-footer__cta-lead">
              Open the workspace, or run the whole stack yourself. No account, no trial and
              no hosted dependency.
            </p>
          </div>
          <div className="l-footer__cta-actions">
            <Magnetic>
              <a className="l-button l-button--primary l-button--large" href="/">
                Get started
                <ArrowRight size={16} aria-hidden="true" />
              </a>
            </Magnetic>
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

        <div className="l-container l-footer__grid">
          <div className="l-footer__brand">
            <a className="l-footer__lockup" href="/welcome" aria-label="CareerOS home">
              <Brand />
            </a>
            <p className="l-footer__tagline">
              Open-source career intelligence. Self-hosted, single-tenant and built to be
              inspected.
            </p>
            <p className="l-footer__maker">
              Designed and built by{' '}
              <a href={AUTHOR.github} target="_blank" rel="noreferrer">
                {AUTHOR.name}
              </a>
              <span className="l-footer__place">{AUTHOR.location}</span>
            </p>
            <div className="l-footer__contact">
              <a href={AUTHOR.portfolio} target="_blank" rel="noreferrer">
                Portfolio
              </a>
              <span aria-hidden="true">/</span>
              <a href={AUTHOR.linkedin} target="_blank" rel="noreferrer">
                LinkedIn
              </a>
              <span aria-hidden="true">/</span>
              <a href={`mailto:${AUTHOR.email}`}>Email</a>
              <span aria-hidden="true">/</span>
              <a href={AUTHOR.github} target="_blank" rel="noreferrer">
                GitHub
              </a>
            </div>
          </div>
          <nav className="l-footer__col" aria-label="Product">
            <h2 className="l-footer__heading">Product</h2>
            <a href="#discover">Discover</a>
            <a href="#track">Track</a>
            <a href="#resume">Resume Studio</a>
            <a href="#interviews">Interviews</a>
            <a href="#open-source">Open source</a>
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
        <div className="l-footer__wordmark" aria-hidden="true">
          CareerOS
        </div>
        <div className="l-container l-footer__bottom">
          <span>Apache-2.0</span>
          <span>© 2026 CareerOS</span>
          <span>React, FastAPI, PostgreSQL</span>
        </div>
      </footer>
      <DevAnnotation />
    </div>
  );
};

export default LandingPage;
