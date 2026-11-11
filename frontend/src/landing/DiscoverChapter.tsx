import { useMemo, useState } from 'react';
import { Compass, SlidersHorizontal } from 'lucide-react';
import { OPPORTUNITIES } from './content';

const FILTERS = ['All', 'Remote', '80+ match'] as const;
type Filter = (typeof FILTERS)[number];

export const DiscoverChapter = () => {
  const [filter, setFilter] = useState<Filter>('All');
  const [activeId, setActiveId] = useState('linear');
  const [saved, setSaved] = useState<ReadonlySet<string>>(() => new Set(['linear']));

  const opportunities = useMemo(
    () =>
      OPPORTUNITIES.filter((opportunity) => {
        if (filter === 'All') return true;
        if (filter === 'Remote') return opportunity.location === 'Remote';
        return opportunity.score >= 80;
      }),
    [filter],
  );

  const active = opportunities.find((opportunity) => opportunity.id === activeId) ?? opportunities[0];

  const toggleSave = () => {
    if (!active) return;
    setSaved((current) => {
      const next = new Set(current);
      if (next.has(active.id)) next.delete(active.id);
      else next.add(active.id);
      return next;
    });
  };

  return (
    <section id="discover" className="l-chapter" aria-labelledby="discover-title">
      <div className="l-container l-chapter__grid">
        <div className="l-chapter__copy">
          <h2 id="discover-title" className="l-h2">
            Find opportunities worth your attention.
          </h2>
          <p className="l-lead">
            Every ATS board is checked on your cadence, normalized into one feed and ranked against
            your profile. You read four roles, not four hundred.
          </p>
          <ul className="l-check-list">
            <li>Hybrid full-text and pgvector match scoring</li>
            <li>Greenhouse, Lever, Ashby, SmartRecruiters, Remotive, Remote OK, RSS, manual import</li>
            <li>Saved searches, ranking snapshots and source health</li>
          </ul>
        </div>

        <div className="demo" aria-label="Illustrative opportunity feed demonstration">
          <div className="demo__bar">
            <span className="demo__title">
              <Compass size={13} aria-hidden="true" />
              Opportunities
            </span>
            <span className="demo__chip">{saved.size} saved</span>
            <span className="demo__chip demo__chip--quiet">Illustrative</span>
          </div>

          <div className="demo__tabs" role="group" aria-label="Filter feed">
            <SlidersHorizontal size={12} aria-hidden="true" />
            {FILTERS.map((option) => (
              <button
                key={option}
                type="button"
                className={`demo__tab${filter === option ? ' is-active' : ''}`}
                aria-pressed={filter === option}
                onClick={() => setFilter(option)}
              >
                {option}
              </button>
            ))}
          </div>

          <div className="demo__split">
            <div className="demo__list" role="group" aria-label="Opportunity list">
              {opportunities.map((opportunity) => (
                <button
                  key={opportunity.id}
                  type="button"
                  className={`demo__opp${active?.id === opportunity.id ? ' is-active' : ''}`}
                  aria-pressed={active?.id === opportunity.id}
                  onClick={() => setActiveId(opportunity.id)}
                >
                  <span className="demo__score">{opportunity.score}</span>
                  <span className="demo__opp-copy">
                    <span className="demo__opp-title">{opportunity.role}</span>
                    <span className="demo__opp-meta">
                      {opportunity.company} · {opportunity.meta}
                    </span>
                  </span>
                </button>
              ))}
              {opportunities.length === 0 ? <p className="demo__empty">No roles match this filter.</p> : null}
            </div>

            {active ? (
              <div className="demo__detail" aria-live="polite">
                <p className="demo__detail-company">{active.company}</p>
                <p className="demo__detail-role">{active.role}</p>
                <p className="demo__detail-meta">
                  {active.meta} · via {active.source}
                </p>
                <p className="demo__detail-match">
                  Matched on{' '}
                  {active.match.map((skill, index) => (
                    <span key={skill} className="demo__skill">
                      {skill}
                      {index < active.match.length - 1 ? ', ' : ''}
                    </span>
                  ))}
                </p>
                <div className="demo__detail-row">
                  <span className="demo__score demo__score--large">{active.score}</span>
                  <div className="demo__detail-actions">
                    <button
                      type="button"
                      className="demo__save"
                      aria-pressed={saved.has(active.id)}
                      onClick={toggleSave}
                    >
                      {saved.has(active.id) ? 'Saved' : 'Save opportunity'}
                    </button>
                    <a className="l-text-link" href="#resume">
                      Tailor resume
                    </a>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <p className="demo__footnote">Illustrative sample feed. Matching runs on your instance, not a hosted service.</p>
        </div>
      </div>
    </section>
  );
};
