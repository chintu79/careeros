import {
  Bell,
  ChevronDown,
  Command,
  Compass,
  FileText,
  LayoutDashboard,
  MessagesSquare,
  Search,
  Sparkles,
  SquareKanban,
  TrendingUp,
} from 'lucide-react';

const RAIL = [
  { icon: LayoutDashboard, label: 'Overview', active: true },
  { icon: Compass, label: 'Discover' },
  { icon: SquareKanban, label: 'Applications' },
  { icon: FileText, label: 'Resume Studio' },
  { icon: MessagesSquare, label: 'Interviews' },
  { icon: TrendingUp, label: 'Insights' },
];

const KPIS = [
  { label: 'Applications', value: '24', delta: '+3 this week' },
  { label: 'Interviews', value: '6', delta: '2 scheduled' },
  { label: 'Offers', value: '2', delta: '1 negotiating' },
  { label: 'Response rate', value: '38%', delta: '+6 pts' },
];

const COLUMNS = [
  { label: 'Saved', count: 12, cards: ['Linear', 'Vercel'] },
  { label: 'Applied', count: 24, cards: ['Stripe', 'Figma'] },
  { label: 'Interviewing', count: 6, cards: ['Notion'] },
];

const NEEDS = [
  { title: 'Follow up with Linear', meta: 'Applied 9 days ago', tone: 'violet' },
  { title: 'Prepare for Stripe interview', meta: 'Thursday, 14:00', tone: 'mint' },
  { title: 'Review resume variant', meta: 'Draft, 2 suggestions', tone: 'plain' },
];

export const ProductFrame = () => (
  <div
    className="pf"
    role="img"
    aria-label="Illustrative CareerOS overview: 24 applications, 6 interviews, 2 offers, a pipeline board and a list of tasks that need attention."
  >
    <div className="pf__shell">
      <aside className="pf__rail" aria-hidden="true">
        <span className="pf__rail-mark">
          <Command size={14} strokeWidth={2.2} />
        </span>
        <span className="pf__rail-divider" />
        {RAIL.map(({ icon: Icon, label, active }) => (
          <span key={label} className={`pf__rail-item${active ? ' is-active' : ''}`} title={label}>
            <Icon size={15} strokeWidth={1.8} />
          </span>
        ))}
      </aside>

      <div className="pf__body">
        <div className="pf__bar">
          <span className="pf__crumb">
            CareerOS <span className="pf__crumb-sep">/</span> Overview
          </span>
          <span className="pf__right">
            <span className="pf__sample">Sample workspace</span>
            <span className="pf__icon-button" aria-hidden="true">
              <Bell size={13} />
            </span>
            <span className="pf__avatar" aria-hidden="true">
              AK
            </span>
          </span>
        </div>

        <div className="pf__main">
          <div className="pf__head">
            <div>
              <p className="pf__kicker">Snapshot</p>
              <p className="pf__title">Overview</p>
            </div>
            <span className="pf__ask">
              <Sparkles size={12} aria-hidden="true" />
              Ask CareerOS
            </span>
          </div>

          <div className="pf__kpis">
            {KPIS.map((kpi) => (
              <div className="pf__kpi" key={kpi.label}>
                <span className="pf__kpi-label">{kpi.label}</span>
                <span className="pf__kpi-value">{kpi.value}</span>
                <span className="pf__kpi-delta">{kpi.delta}</span>
              </div>
            ))}
          </div>

          <div className="pf__split">
            <div className="pf__board">
              <div className="pf__section-head">
                <span>Pipeline</span>
                <span className="pf__section-meta">All roles</span>
              </div>
              <div className="pf__columns">
                {COLUMNS.map((column) => (
                  <div className="pf__column" key={column.label}>
                    <div className="pf__column-head">
                      <span>{column.label}</span>
                      <span className="pf__count">{column.count}</span>
                    </div>
                    {column.cards.map((card) => (
                      <div className="pf__card" key={card}>
                        <span className="pf__card-title">{card}</span>
                        <span className="pf__card-line" />
                        <span className="pf__card-line pf__card-line--short" />
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>

            <div className="pf__needs">
              <div className="pf__section-head">
                <span>Needs you today</span>
                <span className="pf__section-meta">3</span>
              </div>
              <div className="pf__needs-list">
                {NEEDS.map((item) => (
                  <div className="pf__need" key={item.title}>
                    <span className={`pf__dot pf__dot--${item.tone}`} aria-hidden="true" />
                    <span className="pf__need-copy">
                      <span className="pf__need-title">{item.title}</span>
                      <span className="pf__need-meta">{item.meta}</span>
                    </span>
                    <ChevronDown size={11} className="pf__need-chevron" aria-hidden="true" />
                  </div>
                ))}
              </div>
              <div className="pf__search">
                <Search size={11} aria-hidden="true" />
                <span>Search opportunities</span>
                <span className="pf__search-key">⌘K</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
);
