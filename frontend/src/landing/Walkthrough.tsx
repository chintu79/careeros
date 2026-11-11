import { useRef, useState, type KeyboardEvent } from 'react';
import { ArrowRight, Check, Filter, Search } from 'lucide-react';
import { STAGES } from './content';

const STAGE_PANELS = {
  discover: (
    <div className="wk-ui wk-ui--discover" aria-hidden="true">
      <div className="wk-toolbar">
        <span className="wk-search">
          <Search size={12} /> Search roles
        </span>
        <span className="wk-chip">
          <Filter size={11} /> Remote
        </span>
        <span className="wk-chip">Internship</span>
        <span className="wk-chip wk-chip--quiet">Match 80+</span>
      </div>
      {[
        { company: 'Linear', role: 'Backend Engineering Intern', score: '92', meta: 'Remote, Summer 2027' },
        { company: 'Stripe', role: 'Platform Engineering Intern', score: '87', meta: 'Bengaluru, 6 months' },
        { company: 'Notion', role: 'Product Engineer, New Grad', score: '81', meta: 'Hybrid, Full time' },
      ].map((row) => (
        <div className="wk-row" key={row.company}>
          <span className="wk-company">{row.company.slice(0, 1)}</span>
          <span className="wk-row__copy">
            <span className="wk-row__title">{row.role}</span>
            <span className="wk-row__meta">{row.meta}</span>
          </span>
          <span className="wk-score">{row.score}</span>
          <span className="wk-save">Save</span>
        </div>
      ))}
    </div>
  ),
  organize: (
    <div className="wk-ui wk-ui--organize" aria-hidden="true">
      {[
        { label: 'Saved', cards: [['Linear', 'Backend intern'], ['Vercel', 'Platform intern']] },
        { label: 'Applied', cards: [['Stripe', 'Applied 9 days']] },
        { label: 'Interview', cards: [['Notion', 'Thursday, 14:00']] },
        { label: 'Offer', cards: [['Figma', 'Reviewing']] },
      ].map((column) => (
        <div className="wk-column" key={column.label}>
          <span className="wk-column__label">{column.label}</span>
          {column.cards.map(([title, meta]) => (
            <span className="wk-card" key={title}>
              <span className="wk-card__title">{title}</span>
              <span className="wk-card__meta">{meta}</span>
            </span>
          ))}
        </div>
      ))}
    </div>
  ),
  progress: (
    <div className="wk-ui wk-ui--progress" aria-hidden="true">
      <div className="wk-progress-head">
        <span>Pipeline conversion</span>
        <span className="wk-progress-meta">Last 90 days</span>
      </div>
      {[
        { label: 'Applied', value: 24, width: '100%' },
        { label: 'Screen', value: 11, width: '72%' },
        { label: 'Interview', value: 6, width: '48%' },
        { label: 'Offer', value: 2, width: '24%' },
      ].map((stage) => (
        <div className="wk-stage" key={stage.label}>
          <span className="wk-stage__label">{stage.label}</span>
          <span className="wk-stage__track">
            <span style={{ width: stage.width }} />
          </span>
          <span className="wk-stage__value">{stage.value}</span>
        </div>
      ))}
      <div className="wk-source-row">
        <span>
          <Check size={11} /> Greenhouse
        </span>
        <span className="wk-source-score">42 responses</span>
      </div>
      <div className="wk-source-row">
        <span>
          <Check size={11} /> Lever
        </span>
        <span className="wk-source-score">18 responses</span>
      </div>
    </div>
  ),
} as const;

type StageId = keyof typeof STAGE_PANELS;

export const Walkthrough = () => {
  const [active, setActive] = useState<StageId>('discover');
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = STAGES.findIndex((stage) => stage.id === active);
    let next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % STAGES.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + STAGES.length) % STAGES.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = STAGES.length - 1;
    else return;
    event.preventDefault();
    const stage = STAGES[next];
    setActive(stage.id as StageId);
    tabRefs.current[next]?.focus();
  };

  const current = STAGES.find((stage) => stage.id === active) ?? STAGES[0];

  return (
    <div className="wk">
      <div className="wk-tabs" role="tablist" aria-label="Product walkthrough" onKeyDown={onKeyDown}>
        {STAGES.map((stage, index) => (
          <button
            key={stage.id}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            id={`walkthrough-tab-${stage.id}`}
            role="tab"
            type="button"
            aria-selected={stage.id === active}
            aria-controls={`walkthrough-panel-${stage.id}`}
            tabIndex={stage.id === active ? 0 : -1}
            className={`wk-tab${stage.id === active ? ' is-active' : ''}`}
            onClick={() => setActive(stage.id as StageId)}
          >
            <span className="wk-tab__index">{stage.index}</span>
            {stage.label}
          </button>
        ))}
      </div>

      <div
        id={`walkthrough-panel-${active}`}
        role="tabpanel"
        aria-labelledby={`walkthrough-tab-${active}`}
        tabIndex={0}
        className="wk-stage-panel"
      >
        <div className="wk-copy">
          <h3 className="wk-title">{current.title}</h3>
          <p className="wk-body">{current.body}</p>
          <ul className="wk-list">
            {current.bullets.map((bullet) => (
              <li key={bullet}>{bullet}</li>
            ))}
          </ul>
          <a className="l-text-link" href="/">
            Open the workspace <ArrowRight size={14} aria-hidden="true" />
          </a>
        </div>
        <div className="wk-visual" key={active}>
          {STAGE_PANELS[active]}
        </div>
      </div>
    </div>
  );
};
