import { ProductFrame } from './ProductFrame';
import { withScrollScene, gsap } from './motion';
import { trackSpotlight } from './fx/Spotlight';
import { useEffect, useRef } from 'react';

const STEPS = [
  { index: '01', href: '#discover', name: 'Discover', caption: 'Score 92 via Greenhouse · Remote · Summer 2027' },
  { index: '02', href: '#track', name: 'Track', caption: 'Backend Engineering Intern · Assessment round' },
  { index: '03', href: '#resume', name: 'Resume Studio', caption: 'Variant audited against the posting · 3 fixes' },
  { index: '04', href: '#interviews', name: 'Interviews', caption: 'System design · Thu 14:00 · 3 drills queued' },
  { index: '05', href: '#insights', name: 'Insights', caption: 'Rank 14 of 26 · 38% response rate' },
] as const;

export const ConnectedChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.ch02__trail > *', {
          opacity: 0,
          y: 16,
          duration: 0.5,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 70%' },
        });
        gsap.fromTo(
          '.ch02__path-fill',
          { scaleY: 0 },
          {
            scaleY: 1,
            duration: 1.1,
            ease: 'power2.inOut',
            scrollTrigger: { trigger: '.ch02__steps', start: 'top 80%' },
          },
        );
        gsap.from('.ch02__step', {
          opacity: 0,
          y: 12,
          duration: 0.4,
          stagger: 0.12,
          ease: 'power2.out',
          scrollTrigger: { trigger: '.ch02__steps', start: 'top 78%' },
        });
        gsap.from('.ch02__frame', {
          opacity: 0,
          y: 24,
          scale: 0.97,
          duration: 0.6,
          ease: 'power2.out',
          scrollTrigger: { trigger: '.ch02__side', start: 'top 80%' },
        });
      }),
    [],
  );

  return (
    <section id="workspace" ref={scope} className="l-chapter ch02" aria-labelledby="workspace-title">
      <div className="l-container ch02__grid2">
        <div className="ch02__trail">
          <h2 id="workspace-title" className="l-h2">
            One opportunity, followed from first search to signed offer.
          </h2>
          <p className="l-lead">
            Every chapter on this page runs on the same sample record. The role you find on
            Greenhouse is the one you track, tailor a resume for, prepare for and measure.
          </p>
          <ol className="ch02__steps" aria-label="The same sample opportunity across five chapters">
            <li aria-hidden="true" className="ch02__path">
              <span className="ch02__path-fill" />
            </li>
            {STEPS.map((step) => (
              <li key={step.index} className="ch02__step">
                <a className="ch02__step-link" href={step.href}>
                  <span className="ch02__dot" aria-hidden="true">
                    {step.index}
                  </span>
                  <span className="ch02__step-name">{step.name}</span>
                  <span className="ch02__step-caption">{step.caption}</span>
                </a>
              </li>
            ))}
          </ol>
        </div>

        <div className="ch02__side">
          <div className="ch02__frame" onPointerMove={trackSpotlight}>
            <ProductFrame />
          </div>
          <p className="ch02__caption">
            Illustrative sample record: Linear, Backend Engineering Intern. Not real account data.
          </p>
        </div>
      </div>
    </section>
  );
};
