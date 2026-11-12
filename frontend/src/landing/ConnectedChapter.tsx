import { ProductFrame } from './ProductFrame';
import { withScrollScene, gsap } from './motion';
import { trackSpotlight } from './fx/Spotlight';
import { useEffect, useRef } from 'react';

const STEPS = [
  { index: '01', href: '#discover', name: 'Discover', caption: 'One posted role becomes a record' },
  { index: '02', href: '#track', name: 'Track', caption: 'Stages without the spreadsheet' },
  { index: '03', href: '#resume', name: 'Resume Studio', caption: 'A master LaTeX entry, tailored' },
  { index: '04', href: '#interviews', name: 'Interviews', caption: 'Prep attached to the role' },
  { index: '05', href: '#insights', name: 'Insights', caption: 'A funnel you can actually read' },
] as const;

export const ConnectedChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.ch02__head > *', {
          opacity: 0,
          y: 18,
          duration: 0.5,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 70%' },
        });
        // The record trail draws itself once on entry; the nodes resolve along it.
        gsap.fromTo(
          '.ch02__path-fill',
          { scaleX: 0 },
          {
            scaleX: 1,
            duration: 1.1,
            ease: 'power2.inOut',
            scrollTrigger: { trigger: '.ch02__steps', start: 'top 78%' },
          },
        );
        gsap.from('.ch02__step', {
          opacity: 0,
          y: 10,
          duration: 0.4,
          stagger: 0.14,
          ease: 'power2.out',
          scrollTrigger: { trigger: '.ch02__steps', start: 'top 76%' },
        });
        gsap.from('.ch02__frame', {
          opacity: 0,
          y: 26,
          scale: 0.97,
          duration: 0.6,
          ease: 'power2.out',
          scrollTrigger: { trigger: '.ch02__framewrap', start: 'top 80%' },
        });
      }),
    [],
  );

  return (
    <section id="workspace" ref={scope} className="l-chapter ch02" aria-labelledby="workspace-title">
      <div className="l-container ch02__head">
        <h2 id="workspace-title" className="l-h2">
          Everything starts making sense when it works together.
        </h2>
        <p className="l-lead">
          CareerOS is not a pile of features. The same role you discover is the role you track,
          tailor a resume for, prepare for and measure: one record from first search to signed offer.
        </p>
      </div>

      <div className="l-container ch02__scene">
        <div className="ch02__rail" aria-hidden="true">
          <span className="ch02__path-fill" />
        </div>
        <ol className="ch02__steps" aria-label="The CareerOS record trail">
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

        <div className="ch02__framewrap">
          <div className="ch02__frame" onPointerMove={trackSpotlight}>
            <ProductFrame />
          </div>
        </div>
      </div>

      <p className="l-container ch02__sample">
        One record, kept current. Linear, Backend Engineering Intern, score 92. Illustrative sample.
      </p>
    </section>
  );
};
