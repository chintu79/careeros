import { useEffect, useRef } from 'react';
import { Activity, TrendingUp } from 'lucide-react';
import { ACTIVITY, FUNNEL, SOURCES } from './content';
import { withScrollScene, gsap } from './motion';

export const InsightsChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.insights__bar', {
          scaleX: 0,
          transformOrigin: 'left center',
          duration: 0.6,
          ease: 'power2.out',
          stagger: 0.09,
          scrollTrigger: { trigger: scope.current, start: 'top 68%' },
        });
      }),
    [],
  );

  return (
    <section id="insights" ref={scope} className="l-chapter" aria-labelledby="insights-title">
      <div className="l-container l-chapter__grid">
        <div className="l-chapter__copy">
          <h2 id="insights-title" className="l-h2">
            Your progress deserves more than guesswork.
          </h2>
          <p className="l-lead">
            Every application you already track feeds the funnel. No exports, no dashboards to
            decorate: response by source, conversion by stage and a timeline of what happened.
          </p>
          <ul className="l-check-list">
            <li>Response and interview rates by source and stage</li>
            <li>A Sankey flow across saved, applied, screen, interview and offer</li>
            <li>Ranking snapshots show exactly what the match changed</li>
          </ul>
        </div>

        <div className="insights" aria-label="Illustrative career insights demonstration">
          <div className="demo__bar">
            <span className="demo__title">
              <TrendingUp size={13} aria-hidden="true" />
              Candidate funnel
            </span>
            <span className="demo__chip demo__chip--quiet">Illustrative</span>
          </div>

          <div className="insights__funnel">
            {FUNNEL.map((stage) => (
              <div className="insights__row" key={stage.label}>
                <span className="insights__label">{stage.label}</span>
                <span className="insights__track">
                  <span className="insights__bar insights__bar--funnel" style={{ width: stage.width }} />
                </span>
                <span className="insights__value">{stage.value}</span>
              </div>
            ))}
          </div>

          <div className="insights__lower">
            <div className="insights__sources">
              <p className="insights__subhead">Response by source</p>
              {SOURCES.map((source) => (
                <div className="insights__row" key={source.label}>
                  <span className="insights__label">{source.label}</span>
                  <span className="insights__track">
                    <span className="insights__bar insights__bar--source" style={{ width: source.width }} />
                  </span>
                  <span className="insights__value">{source.value}</span>
                </div>
              ))}
            </div>

            <div className="insights__activity">
              <p className="insights__subhead">
                <Activity size={12} aria-hidden="true" />
                Activity
              </p>
              <ol>
                {ACTIVITY.map((event) => (
                  <li key={event.date}>
                    <span className="insights__date">{event.date}</span>
                    {event.label}
                  </li>
                ))}
              </ol>
            </div>
          </div>

          <p className="demo__footnote">Illustrative figures. Your instance shows your own history.</p>
        </div>
      </div>
    </section>
  );
};
