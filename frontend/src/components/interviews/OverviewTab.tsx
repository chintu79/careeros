import React, { useEffect, useState } from 'react';
import {
  BookOpen,
  Sparkles,
  TrendingUp,
  AlertTriangle,
  Calendar,
  Play,
  Target,
  ShieldCheck,
} from 'lucide-react';
import { fetchInterviewAnalytics, fetchPracticeSessions, fetchInterviews } from '../../services/api';
import type { InterviewJournalRecord } from '../../types';

interface OverviewTabProps {
  onNavigateToPractice: () => void;
  onNavigateToJournal: () => void;
  onNavigateToPreparation: () => void;
}

// Zero-fabrication overview: every number comes from the interviews API,
// the analytics computation, or the practice-sessions list. Nothing is invented.
export const OverviewTab: React.FC<OverviewTabProps> = ({
  onNavigateToPractice,
  onNavigateToJournal,
  onNavigateToPreparation,
}) => {
  const [analytics, setAnalytics] = useState<any | null>(null);
  const [practice, setPractice] = useState<{ total: number; items: any[] } | null>(null);
  const [recent, setRecent] = useState<InterviewJournalRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [ana, prac, entries] = await Promise.all([
          fetchInterviewAnalytics().catch(() => null),
          fetchPracticeSessions({ page: 1, page_size: 5 }).catch(() => null),
          fetchInterviews({ page: 1, page_size: 4 }).catch(() => null),
        ]);
        if (cancelled) return;
        setAnalytics(ana);
        setPractice(prac ? { total: prac.total ?? (prac.items?.length ?? 0), items: prac.items || [] } : null);
        setRecent(entries?.items || []);
      } catch (err: any) {
        if (!cancelled) setError(err?.message || 'Could not load preparation overview.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  const total = analytics?.total_interviews ?? 0;
  const difficulty = analytics?.avg_difficulty ?? null;
  const performance = analytics?.avg_performance ?? null;
  const signals = analytics?.funnel_metrics;
  const qaScore = analytics?.qa_quality_score ?? null;

  return (
    <div className="space-y-4">
      {/* Read the room first. */}
      <section aria-label="Preparation snapshot">
        <div className="rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)] p-4 sm:p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <h2 className="section-title">Today in the practice room</h2>
              <p className="mt-1 max-w-prose text-[12px] leading-relaxed text-[var(--color-ink-2)]">
                {total === 0
                  ? 'No interview rounds recorded yet. Open the journal after your next round, or practice a question you expect to face.'
                  : `Across ${total} recorded ${total === 1 ? 'round' : 'rounds'}, interviewers have been scoring you on average ${Number(performance).toFixed(1)}/5. Review the details in the journal tab.`}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onNavigateToPreparation}
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded-md border border-[var(--color-rule)] bg-[var(--color-paper-3)] px-3 text-[12px] font-medium text-[var(--color-ink-2)] transition-colors hover:border-[var(--color-rule-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
              >
                <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Prepare for a role</span>
              </button>
              <button
                type="button"
                onClick={onNavigateToJournal}
                className="inline-flex min-h-[34px] items-center gap-1.5 rounded-md border border-[var(--color-rule)] bg-[var(--color-paper-3)] px-3 text-[12px] font-medium text-[var(--color-ink-2)] transition-colors hover:border-[var(--color-rule-2)] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
              >
                <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Open journal</span>
              </button>
            </div>
          </div>

          {/* Numbers only when there is real data, never invented. */}
          {loading ? (
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-hidden="true">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="h-[68px] animate-pulse rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper-3)]" />
              ))}
            </div>
          ) : (
            <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <div className="rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper)] p-3">
                <dt className="field-label">Total rounds</dt>
                <dd className="mt-1 font-outlier text-[22px] font-semibold text-[var(--color-ink)] tnum">{total}</dd>
              </div>
              <div className="rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper)] p-3">
                <dt className="field-label">Avg. difficulty</dt>
                <dd className="mt-1 font-outlier text-[22px] font-semibold text-[var(--color-ink)] tnum">{difficulty != null ? Number(difficulty).toFixed(1) : '—'}</dd>
              </div>
              <div className="rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper)] p-3">
                <dt className="field-label">Avg. performance</dt>
                <dd className="mt-1 font-outlier text-[22px] font-semibold text-[var(--color-ink)] tnum">{performance != null ? Number(performance).toFixed(1) : '—'}</dd>
              </div>
              <div className="rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper)] p-3">
                <dt className="field-label">Practice sessions</dt>
                <dd className="mt-1 font-outlier text-[22px] font-semibold text-[var(--color-ink)] tnum">{practice ? practice.total : '—'}</dd>
              </div>
            </dl>
          )}
          {error && (
            <p role="alert" className="mt-3 flex items-center gap-1.5 text-[11px] text-[var(--color-error)]">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />
              {error}
            </p>
          )}
        </div>
      </section>

      {/* Rounds outcome and near-just action */}
      <div className="grid gap-3 lg:grid-cols-12">
        <section aria-label="Rounds outcome" className="lg:col-span-7 rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)] p-4 sm:p-5">
          <h3 className="section-title">Where rounds stand</h3>
          <p className="mt-0.5 text-[11px] text-[var(--color-muted)]">Counted from your journal only.</p>
          <ul className="mt-3 divide-y divide-[var(--color-rule-2)]">
            {[
              { label: 'Passed or offered', count: (signals?.passed ?? 0) + (signals?.offer ?? 0) },
              { label: 'Waiting on a decision', count: signals?.pending ?? 0 },
              { label: 'Did not move forward', count: signals?.rejected ?? 0 },
              { label: 'Withdrawn', count: signals?.withdrawn ?? 0 },
            ].map((row) => (
              <li key={row.label} className="flex items-center justify-between gap-3 py-2.5 first:pt-1 last:pb-1">
                <span className="text-[12px] text-[var(--color-ink-2)]">{row.label}</span>
                <span className="font-outlier text-[12px] text-[var(--color-ink)] tnum">{row.count}</span>
              </li>
            ))}
          </ul>
          {qaScore != null && (
            <div className="mt-3 flex items-center justify-between gap-3 rounded-md border border-[var(--color-rule-2)] bg-[var(--color-paper)] px-3 py-2">
              <div className="min-w-0">
                <p className="field-label">QA quality index</p>
                <p className="mt-0.5 text-[11px] text-[var(--color-muted)]">Composite of your logged rounds</p>
              </div>
              <span className="font-outlier text-[20px] font-semibold text-[var(--color-ink)] tnum">{qaScore}</span>
            </div>
          )}
        </section>

        <section aria-label="Next best move" className="lg:col-span-5 rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)] p-4 sm:p-5">
          <h3 className="section-title">What to focus on now</h3>
          <ul className="mt-3 space-y-2">
            {(analytics?.preparation_priorities ?? []).slice(0, 3).map((item: string) => (
              <li key={item} className="flex items-start gap-2 text-[12px] leading-relaxed text-[var(--color-ink-2)]">
                <Target className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--color-accent)]" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
            {!analytics && (
              <li className="text-[12px] leading-relaxed text-[var(--color-muted)]">
                Priorities appear here once your record has at least one entry.
              </li>
            )}
          </ul>
          <button
            type="button"
            onClick={onNavigateToPractice}
            className="mt-4 inline-flex min-h-[36px] w-full items-center justify-center gap-1.5 rounded-md border border-[var(--color-rule)] bg-[var(--color-accent-bg)] px-3 text-[12px] font-medium text-[var(--color-accent)] transition-colors hover:bg-[var(--color-accent-bg)]/80 focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
          >
            <Play className="h-3.5 w-3.5" aria-hidden="true" />
            <span>Practice a mock question</span>
          </button>
        </section>
      </div>

      {/* Recent rounds — only when there are any */}
      {recent && recent.length > 0 && (
        <section aria-label="Recent recorded rounds" className="rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)]">
          <div className="flex items-center justify-between gap-2 border-b border-[var(--color-rule-2)] px-4 py-3">
            <h3 className="section-title">Recent rounds</h3>
            <button
              type="button"
              onClick={onNavigateToJournal}
              className="text-[11px] font-medium text-[var(--color-accent)] hover:underline focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
            >
              View all
            </button>
          </div>
          <ul className="divide-y divide-[var(--color-rule-2)]">
            {recent.slice(0, 4).map((entry) => {
              const result = (entry.interview_result || 'pending').toLowerCase();
              return (
                <li key={entry.id} className="flex flex-col gap-1.5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-[var(--color-ink)]">{entry.company_name}</p>
                    <p className="text-[11px] text-[var(--color-muted)]">
                      {entry.round_name}{entry.interview_date ? ` · ${entry.interview_date}` : ''}
                    </p>
                  </div>
                  <span className="w-fit shrink-0 inline-flex items-center rounded-md border border-[var(--color-rule)] px-2 py-0.5 text-[10px] font-medium capitalize text-[var(--color-ink-2)]">
                    {result}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
};
