import type { FeatureVisual as FeatureVisualId } from './content';

const DiscoveryVisual = () => (
  <div className="fv fv--discovery" aria-hidden="true">
    <div className="fv-opp">
      <span className="fv-opp__score">92</span>
      <span className="fv-opp__copy">
        <span className="fv-opp__title">Backend Engineering Intern</span>
        <span className="fv-opp__meta">Linear, Remote, Summer 2027</span>
      </span>
      <span className="fv-opp__bar">
        <span style={{ width: '92%' }} />
      </span>
    </div>
    <div className="fv-opp">
      <span className="fv-opp__score">87</span>
      <span className="fv-opp__copy">
        <span className="fv-opp__title">Platform Engineering Intern</span>
        <span className="fv-opp__meta">Stripe, Bengaluru, 6 months</span>
      </span>
      <span className="fv-opp__bar">
        <span style={{ width: '87%' }} />
      </span>
    </div>
    <div className="fv-opp">
      <span className="fv-opp__score">81</span>
      <span className="fv-opp__copy">
        <span className="fv-opp__title">Product Engineer, New Grad</span>
        <span className="fv-opp__meta">Notion, Hybrid, Full time</span>
      </span>
      <span className="fv-opp__bar">
        <span style={{ width: '81%' }} />
      </span>
    </div>
  </div>
);

const TrackingVisual = () => (
  <div className="fv fv--tracking" aria-hidden="true">
    {[
      { label: 'Applied', cards: ['Stripe', 'Figma'] },
      { label: 'Interview', cards: ['Notion'] },
      { label: 'Offer', cards: ['Linear'] },
    ].map((column) => (
      <div className="fv-column" key={column.label}>
        <span className="fv-column__label">{column.label}</span>
        {column.cards.map((card) => (
          <span className="fv-mini-card" key={card}>
            {card}
          </span>
        ))}
      </div>
    ))}
  </div>
);

const ResumeVisual = () => (
  <div className="fv fv--resume" aria-hidden="true">
    <div className="fv-sheet">
      <span className="fv-sheet__name" />
      <span className="fv-sheet__line" />
      <span className="fv-sheet__line fv-sheet__line--short" />
      <span className="fv-sheet__line fv-sheet__line--accent" />
      <span className="fv-sheet__line" />
      <span className="fv-sheet__line fv-sheet__line--short" />
    </div>
    <div className="fv-audit">
      <span className="fv-audit__label">ATS audit</span>
      <span className="fv-audit__value">3 fixes</span>
      <span className="fv-audit__track">
        <span />
      </span>
    </div>
  </div>
);

const InterviewVisual = () => (
  <div className="fv fv--interview" aria-hidden="true">
    <span className="fv-tag">Practice question</span>
    <p className="fv-question">
      When would a composite index change the plan for this query?
    </p>
    <div className="fv-wave">
      {[6, 14, 9, 18, 12, 20, 8, 15, 11, 17, 7, 13].map((height, index) => (
        <span key={index} style={{ height }} />
      ))}
    </div>
    <span className="fv-note">Evaluated locally with Ollama</span>
  </div>
);

const InsightsVisual = () => (
  <div className="fv fv--insights" aria-hidden="true">
    {[
      { label: 'Applied', value: 24, width: '100%' },
      { label: 'Interview', value: 6, width: '62%' },
      { label: 'Offer', value: 2, width: '34%' },
    ].map((stage) => (
      <div className="fv-stage" key={stage.label}>
        <span className="fv-stage__label">{stage.label}</span>
        <span className="fv-stage__track">
          <span style={{ width: stage.width }} />
        </span>
        <span className="fv-stage__value">{stage.value}</span>
      </div>
    ))}
  </div>
);

const AIVisual = () => (
  <div className="fv fv--ai" aria-hidden="true">
    <div className="fv-command">
      <span className="fv-command__prompt">Ask CareerOS</span>
      <span className="fv-command__text">Which saved roles match a backend internship?</span>
      <span className="fv-command__key">⌘J</span>
    </div>
    <div className="fv-answer">
      <span className="fv-answer__dot" />
      <span className="fv-answer__text">
        4 saved roles score above 80. Two close this week.
      </span>
      <span className="fv-answer__badge">Optional</span>
    </div>
  </div>
);

export const FeatureVisual = ({ visual }: { visual: FeatureVisualId }) => {
  switch (visual) {
    case 'discovery':
      return <DiscoveryVisual />;
    case 'tracking':
      return <TrackingVisual />;
    case 'resume':
      return <ResumeVisual />;
    case 'interviews':
      return <InterviewVisual />;
    case 'insights':
      return <InsightsVisual />;
    case 'ai':
      return <AIVisual />;
    default:
      return null;
  }
};
