import React, { useState, useEffect } from 'react';
import {
  BarChart3,
  TrendingUp,
  Award,
  Clock,
  Layers,
  FileText,
  Globe,
  Info,
  X,
  RefreshCw,
  CheckCircle2
} from 'lucide-react';
import { ApplicationAnalyticsData } from '../../types';
import { fetchApplicationAnalytics } from '../../services/api';

interface ApplicationAnalyticsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ApplicationAnalyticsModal: React.FC<ApplicationAnalyticsModalProps> = ({
  isOpen,
  onClose
}) => {
  const [data, setData] = useState<ApplicationAnalyticsData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadAnalytics = () => {
    setLoading(true);
    setError(null);
    fetchApplicationAnalytics()
      .then((res) => {
        setData(res);
      })
      .catch((err) => {
        console.error('Failed to load application analytics:', err);
        setError('Failed to fetch analytics metrics.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isOpen) {
      loadAnalytics();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-950/85 backdrop-blur-sm overflow-y-auto">
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-4xl w-full max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.07] flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-purple-500/10 border border-purple-500/20 text-sky-300">
              <BarChart3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-[var(--color-ink)] flex items-center space-x-2">
                <span>Application Performance & Funnel Analytics</span>
              </h2>
              <p className="text-xs text-slate-400">
                Data-driven tracking of employer response rates, funnel conversion, and source efficacy.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 rounded-lg text-slate-400 hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] transition min-h-[28px] min-w-[28px] flex items-center justify-center focus-visible:ring-1 focus-visible:ring-emerald-500"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Content body */}
        <div
          tabIndex={0}
          role="region"
          aria-label="Application Analytics Details"
          className="p-4 sm:p-6 overflow-y-auto space-y-6 focus:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500"
        >
          {loading ? (
            <div className="py-20 text-center text-slate-400 text-xs">
              <RefreshCw className="w-6 h-6 mx-auto animate-spin mb-2" />
              Computing pipeline metrics and conversion rates...
            </div>
          ) : error || !data ? (
            <div className="py-12 text-center text-rose-400 text-xs">
              <p>{error || 'No analytics data available.'}</p>
              <button
                type="button"
                onClick={loadAnalytics}
                className="mt-3 px-3 py-1 bg-[var(--color-paper-3)] text-[var(--color-ink)] rounded focus-visible:ring-1 focus-visible:ring-emerald-500"
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              {/* Formula notice banner */}
              <div className="bg-slate-950/80 border border-white/[0.07] rounded-xl p-3 text-xs text-slate-400 space-y-1">
                <div className="flex items-center space-x-2 text-slate-200 font-semibold">
                  <Info className="w-4 h-4 text-sky-300" />
                  <span>Mathematical Precision & Denominator Guardrails</span>
                </div>
                <p className="text-[11px] leading-relaxed">
                  All conversion rates strictly use <strong>submitted applications</strong> ({data.pipeline_counts.submitted_total}) as the denominator. Unapplied drafts ({data.pipeline_counts.ready_to_apply}) are explicitly excluded to prevent denominator distortion.
                </p>
              </div>

              {/* 4 Core Metric KPI Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
                <div className="bg-slate-950 border border-white/[0.07] rounded-xl p-3.5 space-y-1">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center space-x-1">
                    <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
                    <span>Response Rate</span>
                  </span>
                  <div className="text-xl sm:text-2xl font-black text-[var(--color-ink)] font-mono">
                    {data.rates.application_response_rate}%
                  </div>
                  <p className="text-[10px] text-slate-400 truncate" title={data.formula_definitions?.response_rate}>
                    {data.formula_definitions?.response_rate || 'responses / submitted * 100'}
                  </p>
                </div>

                <div className="bg-slate-950 border border-white/[0.07] rounded-xl p-3.5 space-y-1">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center space-x-1">
                    <Layers className="w-3.5 h-3.5 text-sky-300" />
                    <span>Interview Rate</span>
                  </span>
                  <div className="text-xl sm:text-2xl font-black text-sky-300 font-mono">
                    {data.rates.interview_conversion_rate}%
                  </div>
                  <p className="text-[10px] text-slate-400 truncate" title={data.formula_definitions?.interview_rate}>
                    {data.formula_definitions?.interview_rate || 'interviews / submitted * 100'}
                  </p>
                </div>

                <div className="bg-slate-950 border border-white/[0.07] rounded-xl p-3.5 space-y-1">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center space-x-1">
                    <Award className="w-3.5 h-3.5 text-amber-400" />
                    <span>Offer Conversion</span>
                  </span>
                  <div className="text-xl sm:text-2xl font-black text-amber-400 font-mono">
                    {data.rates.offer_conversion_rate}%
                  </div>
                  <p className="text-[10px] text-slate-400 truncate" title={data.formula_definitions?.offer_rate}>
                    {data.formula_definitions?.offer_rate || 'offers / submitted * 100'}
                  </p>
                </div>

                <div className="bg-slate-950 border border-white/[0.07] rounded-xl p-3.5 space-y-1">
                  <span className="text-[11px] text-slate-400 font-medium flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Avg Response Time</span>
                  </span>
                  <div className="text-xl sm:text-2xl font-black text-emerald-400 font-mono">
                    {data.rates.average_response_time_days}d
                  </div>
                  <p className="text-[10px] text-slate-400 truncate">
                    Submission to outcome
                  </p>
                </div>
              </div>

              {/* Pipeline Status Breakdown */}
              <div className="bg-slate-950 border border-white/[0.07] rounded-xl p-4 space-y-3">
                <h3 className="text-xs font-bold text-[var(--color-ink)]  flex items-center space-x-2">
                  <Layers className="w-4 h-4 text-emerald-400" />
                  <span>Pipeline Distribution</span>
                </h3>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-center text-xs">
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Ready</div>
                    <div className="text-sm font-bold text-blue-400">{data.pipeline_counts.ready_to_apply}</div>
                  </div>
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Applied</div>
                    <div className="text-sm font-bold text-emerald-400">{data.pipeline_counts.applied_pending}</div>
                  </div>
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Screening</div>
                    <div className="text-sm font-bold text-teal-400">{data.pipeline_counts.screening}</div>
                  </div>
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Interviewing</div>
                    <div className="text-sm font-bold text-sky-300">{data.pipeline_counts.interviewing}</div>
                  </div>
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Offered</div>
                    <div className="text-sm font-bold text-amber-400">{data.pipeline_counts.offered}</div>
                  </div>
                  <div className="p-2 rounded-lg border border-white/[0.07] bg-[var(--color-paper)]">
                    <div className="text-slate-400 text-[10px]">Rejected</div>
                    <div className="text-sm font-bold text-rose-400">{data.pipeline_counts.rejected}</div>
                  </div>
                </div>
              </div>

              {/* Source-wise Performance Table */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--color-ink)]  flex items-center space-x-2">
                  <Globe className="w-4 h-4 text-blue-400" />
                  <span>Source Platform Performance</span>
                </h3>
                {data.source_performance.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-2">No source data recorded yet.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 border-b border-white/[0.07] text-slate-400 font-semibold">
                        <tr>
                          <th className="p-3">Source Channel</th>
                          <th className="p-3 text-center">Applied</th>
                          <th className="p-3 text-center">Responses</th>
                          <th className="p-3 text-center">Interviews</th>
                          <th className="p-3 text-center">Offers</th>
                          <th className="p-3 text-right">Response Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.06] bg-[var(--color-paper-2)]">
                        {data.source_performance.map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-850">
                            <td className="p-3 font-semibold text-[var(--color-ink)] capitalize">{item.source}</td>
                            <td className="p-3 text-center font-mono text-slate-300">{item.total_applied}</td>
                            <td className="p-3 text-center font-mono text-slate-300">{item.responses}</td>
                            <td className="p-3 text-center font-mono text-sky-300">{item.interviews}</td>
                            <td className="p-3 text-center font-mono text-amber-400">{item.offers}</td>
                            <td className="p-3 text-right font-mono font-bold text-emerald-400">
                              {item.response_rate_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Resume Version Performance Table */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-[var(--color-ink)]  flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-sky-300" />
                  <span>Resume Version Efficacy</span>
                </h3>
                {data.resume_performance.length === 0 ? (
                  <p className="text-xs text-slate-500 italic py-2">No resume-linked applications found yet.</p>
                ) : (
                  <div className="overflow-x-auto rounded-xl border border-white/[0.07]">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-slate-950 border-b border-white/[0.07] text-slate-400 font-semibold">
                        <tr>
                          <th className="p-3">Resume Variant</th>
                          <th className="p-3 text-center">Dispatched</th>
                          <th className="p-3 text-center">Interviews</th>
                          <th className="p-3 text-center">Offers</th>
                          <th className="p-3 text-right">Interview Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/[0.06] bg-[var(--color-paper-2)]">
                        {data.resume_performance.map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-850">
                            <td className="p-3 font-medium text-[var(--color-ink)]">{item.resume_title}</td>
                            <td className="p-3 text-center font-mono text-slate-300">{item.total_applied}</td>
                            <td className="p-3 text-center font-mono text-sky-300">{item.interviews}</td>
                            <td className="p-3 text-center font-mono text-amber-400">{item.offers}</td>
                            <td className="p-3 text-right font-mono font-bold text-sky-300">
                              {item.interview_rate_pct}%
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
