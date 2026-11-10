import React from 'react';
import { CheckCircle2, AlertTriangle, RefreshCw, Zap } from 'lucide-react';
import { ResumeQualityAuditResult } from '../../types';
import { Modal } from '../ui/Modal';

interface QualityAuditModalProps {
  isOpen: boolean;
  onClose: () => void;
  report: ResumeQualityAuditResult | null;
  isLoading: boolean;
  onRefresh: () => void;
}

export const QualityAuditModal: React.FC<QualityAuditModalProps> = ({
  isOpen,
  onClose,
  report,
  isLoading,
  onRefresh
}) => {
  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10';
    if (score >= 80) return 'text-emerald-300 border-emerald-500/25 bg-emerald-500/10';
    if (score >= 70) return 'text-amber-400 border-amber-500/30 bg-amber-500/10';
    return 'text-rose-400 border-rose-500/30 bg-rose-500/10';
  };

  const getGradeBadge = (grade: string) => {
    if (grade === 'A+' || grade === 'A') return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
    if (grade === 'B') return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="3xl"
      title="Pre-Flight ATS Quality Audit"
      description="Automated 6-factor inspection for parsing fidelity, syntax, and action verb strength"
      headerAction={
        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          aria-label="Re-run quality audit"
          aria-busy={isLoading}
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.06] transition disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          title="Re-run audit"
        >
          <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
        </button>
      }
      footer={
        <div className="flex items-center justify-between w-full text-xs text-slate-400">
          <span className="text-[11px] text-slate-500">Targeting Workday, Greenhouse, Lever, and iCIMS parser schemas</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium bg-white/[0.06] hover:bg-white/[0.10] text-slate-200 rounded-lg transition border border-white/[0.08] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            Close Audit
          </button>
        </div>
      }
    >
      <div className="space-y-5">
        {isLoading ? (
          <div className="py-16 flex flex-col items-center justify-center text-slate-400 gap-3">
            <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-sm font-medium text-slate-300">Running 6-factor ATS pre-flight inspection...</p>
          </div>
        ) : report ? (
          <>
            {/* Score Banner */}
            <div className="flex flex-col sm:flex-row items-center justify-between p-4 rounded-xl bg-[var(--color-paper-3)] border border-white/[0.08] gap-4">
              <div className="flex items-center gap-4">
                <div className={`flex flex-col items-center justify-center w-16 h-16 rounded-xl border font-bold text-2xl ${getScoreColor(report.ats_score)}`}>
                  <span>{Math.round(report.ats_score)}</span>
                  <span className="text-[10px] font-semibold opacity-80">Score</span>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-white">ATS Health Assessment</span>
                    <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${getGradeBadge(report.grade)}`}>
                      Grade {report.grade}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 max-w-lg leading-relaxed">
                    {report.summary}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 text-xs bg-[var(--color-paper)] px-3 py-2 rounded-lg border border-white/[0.06] text-slate-300">
                <Zap className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="text-[11px]">Single-column format ensures 100% parse pass rate</span>
              </div>
            </div>

            {/* 6 Quality Checks List */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400">
                Quality Dimension Checklist ({report.checks.filter(c => c.passed).length}/{report.checks.length} Passed)
              </h4>

              <div className="grid grid-cols-1 gap-2.5">
                {report.checks.map((check, idx) => (
                  <div
                    key={idx}
                    className={`p-3.5 rounded-xl border transition-colors ${
                      check.passed
                        ? 'bg-[var(--color-paper-3)]/60 border-white/[0.06]'
                        : 'bg-rose-950/20 border-rose-500/30'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2.5">
                        {check.passed ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                        )}
                        <span className="text-xs font-semibold text-white">{check.title}</span>
                      </div>
                      <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full border ${getScoreColor(check.score)}`}>
                        {Math.round(check.score)}%
                      </span>
                    </div>

                    <div className="pl-6 space-y-1">
                      {check.details.map((detail, dIdx) => (
                        <p key={dIdx} className="text-[11px] text-slate-300 flex items-start gap-1.5 leading-relaxed">
                          <span className="text-slate-500 mt-0.5">•</span>
                          <span>{detail}</span>
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <div className="text-center py-12 text-slate-400">
            <p className="text-xs">No audit report available. Click Refresh to inspect this resume.</p>
          </div>
        )}
      </div>
    </Modal>
  );
};
