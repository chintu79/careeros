import React from 'react';
import { Sparkles, Bookmark, Clock, Layers } from 'lucide-react';
import { SummaryMetrics } from '../../types';
import { CountUp } from '../ui/CountUp';

interface SummaryBannerProps {
  metrics: SummaryMetrics | null;
  onSelectTab: (tab: string) => void;
}

export const SummaryBanner: React.FC<SummaryBannerProps> = ({ metrics, onSelectTab }) => {
  if (!metrics) return null;

  const cards = [
    {
      title: 'Discovered',
      value: metrics.total_discovered,
      subtitle: `${metrics.new_today} added today`,
      icon: Layers,
      tab: 'latest'
    },
    {
      title: 'High match',
      value: metrics.high_match,
      subtitle: '70% and above',
      icon: Sparkles,
      tab: 'recommended'
    },
    {
      title: 'Saved',
      value: metrics.saved,
      subtitle: 'Bookmarked',
      icon: Bookmark,
      tab: 'saved'
    },
    {
      title: 'Expiring',
      value: metrics.expiring_soon,
      subtitle: 'Within 7 days',
      icon: Clock,
      tab: 'expiring'
    }
  ];

  return (
    <div className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-white/[0.07] bg-white/[0.07] lg:grid-cols-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <button
            key={card.title}
            type="button"
            onClick={() => onSelectTab(card.tab)}
            className="group flex flex-col items-start bg-[var(--color-paper)] px-4 py-3.5 text-left transition-colors hover:bg-[var(--color-paper-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-400/60"
          >
            <span className="flex w-full items-center justify-between gap-2">
              <span className="text-[12px] font-medium text-slate-400">{card.title}</span>
              <Icon className="h-3.5 w-3.5 text-slate-600 transition-colors group-hover:text-slate-400" strokeWidth={1.75} aria-hidden="true" />
            </span>
            <span className="stat-value mt-2 text-[28px] font-semibold leading-none text-[var(--color-ink)]">
              <CountUp to={card.value} separator="," duration={0.8} />
            </span>
            <span className="mt-1.5 text-[11px] text-slate-500">{card.subtitle}</span>
          </button>
        );
      })}
    </div>
  );
};
