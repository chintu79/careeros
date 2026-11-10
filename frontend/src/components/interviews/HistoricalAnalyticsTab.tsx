import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  AlertTriangle,
  Award,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  RefreshCw,
  BarChart3,
  Flame,
  Zap,
  Target,
  ArrowUpRight
} from 'lucide-react';
import { HistoricalInterviewAnalytics } from '../../types';
import { fetchInterviewAnalytics } from '../../services/api';

interface HistoricalAnalyticsTabProps {
  onGoToJournal?: () => void;
  onGoToPractice?: () => void;
}

export const HistoricalAnalyticsTab: React.FC<HistoricalAnalyticsTabProps> = ({
  onGoToJournal,
  onGoToPractice
}) => {
  const [analytics, setAnalytics] = useState<HistoricalInterviewAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInterviewAnalytics();
      setAnalytics(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to fetch historical analytics');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-12 text-center space-y-3">
        <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin mx-auto" />
        <div className="text-sm font-semibold text-slate-200">Analyzing Recorded Interview Data...</div>
        <div className="text-xs text-slate-500">
          Synthesizing historical rounds, interviewer feedback, topic frequencies, and outcome ratios.
        </div>
      </div>
    );
  }

  if (error || !analytics) {
    return (
      <div className="bg-rose-950/40 border border-rose-800/60 rounded-xl p-6 text-rose-300 text-xs flex items-center space-x-3">
        <AlertCircle className="w-5 h-5 flex-shrink-0" />
        <span>{error || 'Unable to load interview analytics.'}</span>
      </div>
    );
  }

  const hasInterviews = analytics.total_interviews > 0;

  return (
    <div className="space-y-6">
      {/* Policy Banner: Zero Fabrication */}
      <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-400">
              <ShieldCheck className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">Performance audit</h3>
              <p className="text-xs text-slate-400">
                Diagnostic insights synthesized strictly from your real logged interview records. Zero fabricated metrics.
              </p>
            </div>
          </div>

          <button
            onClick={loadData}
            className="inline-flex min-h-[32px] items-center gap-1.5 self-start rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)] sm:self-auto"
          >
            <RefreshCw className="h-3.5 w-3.5 text-slate-400" />
            <span>Recalculate Audit</span>
          </button>
        </div>
      </div>

      {/* Zero State if no interviews */}
      {!hasInterviews && (
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-8 text-center space-y-4">
          <BarChart3 className="w-12 h-12 text-slate-700 mx-auto" />
          <h4 className="text-base font-bold text-slate-200">No Interview Journal Records Found</h4>
          <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
            {analytics.zero_records_note || "Record your real interview rounds in the Interview Journal tab to populate genuine conversion rates, topic difficulty distributions, and personalized priorities."}
          </p>
          <div className="flex items-center justify-center space-x-3 pt-2">
            <button
              onClick={onGoToJournal}
              className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-bold rounded-lg transition"
            >
              Record First Interview
            </button>
            <button
              onClick={onGoToPractice}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 transition"
            >
              Practice in Simulator
            </button>
          </div>
        </div>
      )}

      {/* KPI Funnel Overview */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4">
          <span className="text-[10px] font-medium text-slate-500 block mb-1">
            Total Interviews
          </span>
          <div className="text-[24px] font-semibold text-[var(--color-ink)]">
            {analytics.total_interviews}
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">Logged rounds</span>
        </div>

        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4">
          <span className="text-[10px] font-medium text-slate-500 block mb-1">
            Conversion Rate
          </span>
          <div className="text-[24px] font-semibold text-emerald-400">
            {analytics.funnel_metrics.conversion_rate_pct}%
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">Passed + Offers</span>
        </div>

        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4">
          <span className="text-[10px] font-medium text-slate-500 block mb-1">
            Avg Difficulty
          </span>
          <div className="text-[24px] font-semibold text-slate-200 tnum">
            {analytics.avg_difficulty} <span className="text-xs text-slate-500 font-normal">/ 5</span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">Perceived challenge</span>
        </div>

        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4">
          <span className="text-[10px] font-medium text-slate-500 block mb-1">
            Performance Rating
          </span>
          <div className="text-[24px] font-semibold text-slate-200 tnum">
            {analytics.avg_performance} <span className="text-xs text-slate-500 font-normal">/ 5</span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">Self-assessed score</span>
        </div>

        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4 col-span-2 md:col-span-1">
          <span className="text-[10px] font-medium text-slate-500 block mb-1">
            QA Quality Index
          </span>
          <div className="text-[24px] font-semibold text-emerald-300">
            {analytics.qa_quality_score} <span className="text-xs text-slate-500 font-normal">/ 100</span>
          </div>
          <span className="text-[11px] text-slate-500 mt-1 block">Composite competency</span>
        </div>
      </div>

      {/* Outcomes Funnel Bar */}
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-5 space-y-3">
        <h4 className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
          <TrendingUp className="h-3.5 w-3.5 text-slate-500" />
          <span>Stage Outcome Distribution</span>
        </h4>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 text-xs">
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
            <span className="field-label block">Offers received</span>
            <div className="mt-1 font-mono text-[15px] font-medium text-[var(--color-ink)] tnum">{analytics.funnel_metrics.offer}</div>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
            <span className="field-label block">Rounds passed</span>
            <div className="mt-1 font-mono text-[15px] font-medium text-[var(--color-ink)] tnum">{analytics.funnel_metrics.passed}</div>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
            <span className="field-label block">Pending decisions</span>
            <div className="mt-1 font-mono text-[15px] font-medium text-[var(--color-ink)] tnum">{analytics.funnel_metrics.pending}</div>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
            <span className="field-label block">Rejections</span>
            <div className="mt-1 font-mono text-[15px] font-medium text-[var(--color-ink)] tnum">{analytics.funnel_metrics.rejected}</div>
          </div>
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
            <span className="field-label block">Withdrawn</span>
            <div className="mt-1 font-mono text-[15px] font-medium text-slate-400 tnum">{analytics.funnel_metrics.withdrawn}</div>
          </div>
        </div>
      </div>

      {/* Main 2-column Analysis Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left: Repeatedly Difficult Topics */}
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
              <Flame className="h-3.5 w-3.5 text-rose-300/80" />
              <span>Repeatedly Difficult Topics</span>
            </h4>
            <span className="text-[11px] text-slate-500 font-medium">Flagged in multiple interviews</span>
          </div>

          {analytics.repeatedly_difficult_topics.length > 0 ? (
            <div className="space-y-2.5">
              {analytics.repeatedly_difficult_topics.map((item, i) => (
                <div
                  key={i}
                  className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-center justify-between"
                >
                  <div>
                    <span className="text-sm font-semibold text-slate-200 block">{item.topic}</span>
                    <span className="text-[11px] text-slate-400">
                      Flagged {item.frequency} times during live evaluations
                    </span>
                  </div>
                  <span className={`px-2.5 py-0.5 rounded text-[11px] font-bold ${
                    item.severity === 'High'
                      ? 'bg-rose-950/80 text-rose-300 border border-rose-800/60'
                      : 'bg-amber-950/80 text-amber-300 border border-amber-800/60'
                  }`}>
                    {item.severity} Priority
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-slate-950/40 rounded-lg text-xs text-slate-400 text-center border border-slate-800/60">
              No recurrent topic bottlenecks detected yet.
            </div>
          )}
        </div>

        {/* Right: Strong Technical Areas */}
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
              <Zap className="h-3.5 w-3.5 text-emerald-300/80" />
              <span>Demonstrated Technical Strengths</span>
            </h4>
            <span className="text-[11px] text-slate-500 font-medium">High performance consistency</span>
          </div>

          {analytics.strong_technical_areas.length > 0 ? (
            <div className="space-y-2.5">
              {analytics.strong_technical_areas.map((item, i) => (
                <div
                  key={i}
                  className="bg-slate-950/60 border border-slate-800/80 rounded-lg p-3 flex items-center justify-between"
                >
                  <div className="space-y-0.5">
                    <span className="text-sm font-semibold text-slate-200 block">{item.topic}</span>
                    <span className="text-[11px] text-emerald-400/90 font-medium">Consistently mastered</span>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-bold text-emerald-400">{item.consistency_score}%</span>
                    <span className="text-[10px] text-slate-500 block">Reliability</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 bg-slate-950/40 rounded-lg text-xs text-slate-400 text-center border border-slate-800/60">
              Log interview ratings to discover your highest scoring technical competencies.
            </div>
          )}
        </div>
      </div>

      {/* Lower Row: Communication Improvement Areas & Preparation Priorities */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Communication Improvements */}
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-5 space-y-3">
          <h4 className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
            <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
            <span>Communication & Delivery Recommendations</span>
          </h4>
          <ul className="space-y-2 text-xs text-slate-300">
            {analytics.communication_improvement_areas.map((tip, i) => (
              <li key={i} className="flex items-start space-x-2 bg-slate-950/40 p-2.5 rounded border border-slate-800/70">
                <span className="text-slate-500 mt-0.5 font-medium">•</span>
                <span className="leading-relaxed">{tip}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Preparation Priorities Roadmap */}
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-5 space-y-3">
          <h4 className="text-xs font-bold text-emerald-300  flex items-center space-x-1.5">
            <Target className="w-4 h-4 text-emerald-300" />
            <span>Targeted Preparation Priorities</span>
          </h4>
          <ul className="space-y-2 text-xs text-slate-300">
            {analytics.preparation_priorities.map((item, i) => (
              <li key={i} className="flex items-start space-x-2 bg-slate-950/40 p-2.5 rounded border border-slate-800/70">
                <span className="text-emerald-300 mt-0.5 font-bold">{i + 1}.</span>
                <span className="leading-relaxed">{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
